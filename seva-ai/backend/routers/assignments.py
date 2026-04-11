import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
import asyncio

from database.connection import get_db
from models.assignment import VolunteerAssignment, AssignmentStatus
from models.volunteer import Volunteer
from models.alert import BioAlert
from models.audit_log import AuditLog
from schemas.assignment import AssignmentCreate, AssignmentResponse
from websocket.socket_manager import socket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assignments", tags=["Assignments"])

# Status progression order
STATUS_ORDER = [
    AssignmentStatus.assigned,
    AssignmentStatus.en_route,
    AssignmentStatus.on_site,
    AssignmentStatus.completed,
]

class AssignmentStatusUpdate(BaseModel):
    status: AssignmentStatus

class AssignmentReviewRequest(BaseModel):
    points: int = Field(..., ge=0, le=100)
    comment: str


def _serialize_assignment(assignment: VolunteerAssignment, volunteer: Volunteer = None, alert: BioAlert = None) -> dict:
    """Serializes an assignment + optional volunteer/alert into a clean dict."""
    result = {
        "id": str(assignment.id),
        "alert_id": str(assignment.alert_id),
        "volunteer_id": str(assignment.volunteer_id),
        "status": assignment.status.value,
        "notes": assignment.notes,
        "points_awarded": getattr(assignment, 'points_awarded', 0),
        "feedback_comment": getattr(assignment, 'feedback_comment', None),
        "assigned_at": (assignment.assigned_at.isoformat() + "Z") if assignment.assigned_at else None,
    }
    if volunteer:
        result["volunteer"] = {
            "id": str(volunteer.id),
            "name": volunteer.name,
            "phone": volunteer.phone,
            "skills": volunteer.skills or [],
            "is_available": volunteer.is_available,
        }
    if alert:
        result["alert"] = {
            "id": str(alert.id),
            "zone_id": str(alert.zone_id) if alert.zone_id else None,
            "severity": alert.severity.value,
            "alert_type": alert.alert_type,
        }
    return result


@router.get("/")
async def get_assignments(
    alert_id: Optional[str] = Query(None),
    volunteer_id: Optional[str] = Query(None),
    status: Optional[AssignmentStatus] = Query(None),
    db: Session = Depends(get_db),
):
    """List assignments, filterable by alert_id, volunteer_id, status."""
    query = db.query(VolunteerAssignment)
    if alert_id:
        query = query.filter(VolunteerAssignment.alert_id == alert_id)
    if volunteer_id:
        query = query.filter(VolunteerAssignment.volunteer_id == volunteer_id)
    if status:
        query = query.filter(VolunteerAssignment.status == status)

    assignments = query.order_by(VolunteerAssignment.assigned_at.desc()).all()
    return [_serialize_assignment(a) for a in assignments]


@router.post("/", status_code=201)
async def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db)):
    """
    Assign a volunteer to an alert:
      1. Validates volunteer exists and is available
      2. Guards against double-assignment on the same alert
      3. Sets volunteer.is_available = False
      4. Creates VolunteerAssignment record
      5. Writes audit log
      6. Emits WebSocket 'volunteer_assigned' event
    """
    volunteer = db.query(Volunteer).filter(Volunteer.id == payload.volunteer_id).first()
    alert = db.query(BioAlert).filter(BioAlert.id == payload.alert_id).first()

    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if not volunteer.is_available:
        raise HTTPException(status_code=409, detail=f"{volunteer.name} is currently deployed and cannot be reassigned.")

    # Guard: prevent double-assignment to the same alert
    existing = db.query(VolunteerAssignment).filter(
        VolunteerAssignment.alert_id == payload.alert_id,
        VolunteerAssignment.volunteer_id == payload.volunteer_id,
        VolunteerAssignment.status != AssignmentStatus.completed,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"{volunteer.name} is already assigned to this alert.")

    # Lock volunteer availability
    volunteer.is_available = False

    assignment = VolunteerAssignment(
        alert_id=payload.alert_id,
        volunteer_id=payload.volunteer_id,
        notes=payload.notes,
        status=AssignmentStatus.assigned,
    )
    db.add(assignment)
    db.flush()  # get assignment.id before commit

    audit = AuditLog(
        action="volunteer_assigned",
        entity_type="VolunteerAssignment",
        entity_id=assignment.id,
        payload={
            "volunteer_id": str(volunteer.id),
            "volunteer_name": volunteer.name,
            "alert_id": str(alert.id),
            "zone_id": str(alert.zone_id) if alert.zone_id else None,
        },
        performed_by="Coordinator",
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)
    db.refresh(volunteer)

    ws_payload = {
        "assignment_id": str(assignment.id),
        "volunteer_id": str(volunteer.id),
        "volunteer_name": volunteer.name,
        "alert_id": str(alert.id),
        "zone_id": str(alert.zone_id) if alert.zone_id else None,
        "status": assignment.status.value,
    }
    asyncio.ensure_future(socket_manager.emit_volunteer_assigned(ws_payload))

    logger.info(f"Assigned {volunteer.name} → alert {alert.id} (assignment {assignment.id})")

    return _serialize_assignment(assignment, volunteer, alert)


@router.patch("/{id}/status")
async def update_assignment_status(id: str, payload: AssignmentStatusUpdate, db: Session = Depends(get_db)):
    """
    Advances the assignment lifecycle:
      assigned → en_route → on_site → completed

    On completion:
      - volunteer.is_available is restored to True
      - A WebSocket 'assignment_completed' event is emitted
      - Audit log is written
    """
    assignment = db.query(VolunteerAssignment).filter(VolunteerAssignment.id == id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    old_status = assignment.status
    new_status = payload.status

    # Enforce forward-only progression (no going backward in the lifecycle)
    try:
        if STATUS_ORDER.index(new_status) < STATUS_ORDER.index(old_status):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot revert status from '{old_status.value}' to '{new_status.value}'"
            )
    except ValueError:
        pass  # Let unknown status through

    assignment.status = new_status

    volunteer: Volunteer | None = None
    if new_status == AssignmentStatus.completed:
        volunteer = db.query(Volunteer).filter(Volunteer.id == assignment.volunteer_id).first()
        if volunteer:
            volunteer.is_available = True
            logger.info(f"Volunteer {volunteer.name} returned to standby after completing assignment {id}")

    audit = AuditLog(
        action="assignment_status_updated",
        entity_type="VolunteerAssignment",
        entity_id=assignment.id,
        payload={"old_status": old_status.value, "new_status": new_status.value},
        performed_by="Coordinator",
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)

    # Emit WebSocket event for real-time UI update
    event_name = "assignment_completed" if new_status == AssignmentStatus.completed else "assignment_status_updated"
    ws_payload = {
        "assignment_id": str(assignment.id),
        "volunteer_id": str(assignment.volunteer_id),
        "alert_id": str(assignment.alert_id),
        "old_status": old_status.value,
        "new_status": new_status.value,
        "volunteer_now_available": new_status == AssignmentStatus.completed,
    }
    asyncio.ensure_future(socket_manager.sio.emit(event_name, ws_payload))

    return _serialize_assignment(assignment, volunteer)

@router.post("/{id}/review")
async def review_assignment(id: str, payload: AssignmentReviewRequest, db: Session = Depends(get_db)):
    """
    Submits a review for a completed assignment, granting points and leaving feedback.
    """
    assignment = db.query(VolunteerAssignment).filter(VolunteerAssignment.id == id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    if assignment.status != AssignmentStatus.completed:
        raise HTTPException(status_code=400, detail="Can only review completed assignments")

    assignment.points_awarded = payload.points
    assignment.feedback_comment = payload.comment
    
    audit = AuditLog(
        action="assignment_reviewed",
        entity_type="VolunteerAssignment",
        entity_id=assignment.id,
        payload={"points": payload.points, "comment": payload.comment},
        performed_by="Coordinator"
    )
    db.add(audit)
    db.commit()
    db.refresh(assignment)
    
    return _serialize_assignment(assignment)
