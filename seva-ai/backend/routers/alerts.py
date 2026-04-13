from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from database.connection import get_db
from models.alert import BioAlert
from models.assignment import VolunteerAssignment, AssignmentStatus
from models.report import FieldReport
from models.audit_log import AuditLog
from models.volunteer import Volunteer
from services.matching_engine import find_matched_volunteers

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("")
async def get_alerts(
    is_active: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    List alerts, defaults to active only. Includes assigned volunteer counts.
    """
    alerts = db.query(BioAlert).filter(BioAlert.is_active == is_active).all()
    results = []
    
    for alert in alerts:
        # count active assignments per alert
        count = db.query(func.count(VolunteerAssignment.id)).filter(
            VolunteerAssignment.alert_id == alert.id
        ).scalar()
        
        results.append({
            "alert": alert,
            "assigned_volunteers_count": count or 0
        })
        
    return results

@router.get("/{id}")
async def get_alert(id: str, db: Session = Depends(get_db)):
    """
    Extracts deep metadata on a single alert incorporating triggers, assignments, and AI matches.
    """
    alert = db.query(BioAlert).filter(BioAlert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    # Triggered reports lookup:
    reports = []
    if alert.triggered_by_reports:
        # e.g. triggered_by_reports might just be the categories, 
        # or if it implies specific reports in actual data
        # the model stores unique_markers. We will just return the markers directly
        # and fetch recent reports matching those markers from the zone
        pass
        
    recent_reports = db.query(FieldReport).filter(
        FieldReport.zone_id == alert.zone_id
    ).order_by(FieldReport.reported_at.desc()).limit(10).all()
    
    # Existing assignments
    assignments = db.query(VolunteerAssignment).filter(VolunteerAssignment.alert_id == id).all()
    
    # Run the matching engine automatically
    matched_volunteers = find_matched_volunteers(db, alert, limit=5)
    
    return {
        "alert": alert,
        "triggered_by_categories": alert.triggered_by_reports,
        "recent_zone_reports": recent_reports,
        "assigned_volunteers": assignments,
        "matching_engine_results": matched_volunteers
    }

@router.put("/{id}/resolve")
async def resolve_alert(id: str, db: Session = Depends(get_db)):
    """
    Mark an active BioAlert strictly as resolved. Upates any assigned volunteers back to standby.
    """
    alert = db.query(BioAlert).filter(BioAlert.id == id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    alert.is_active = False
    
    # Set all active assignments for this alert to completed
    assignments = db.query(VolunteerAssignment).filter(
        VolunteerAssignment.alert_id == id,
        VolunteerAssignment.status != AssignmentStatus.completed
    ).all()
    
    for asn in assignments:
        asn.status = AssignmentStatus.completed
        v = db.query(Volunteer).filter(Volunteer.id == asn.volunteer_id).first()
        if v:
            v.is_available = True
    
    audit = AuditLog(
        action="alert_resolved",
        entity_type="BioAlert",
        entity_id=alert.id,
        performed_by="System"
    )
    db.add(audit)
    db.commit()
    db.refresh(alert)
    
    return {"message": "Alert resolved, volunteers stand by.", "alert": alert}
