import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database.connection import get_db
from models.volunteer import Volunteer
from models.alert import BioAlert
from models.audit_log import AuditLog
from schemas.volunteer import (
    VolunteerCreate, VolunteerResponse,
    VolunteerAvailabilityUpdate, LocationUpdate
)
from services.matching_engine import find_matched_volunteers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/volunteers", tags=["Volunteers"])


# ─── Helper ──────────────────────────────────────────────────────────────────

def _build_point_wkt(lat: float, lon: float) -> str:
    """Returns a WKT POINT string suitable for GeoAlchemy2 insertion."""
    return f"SRID=4326;POINT({lon} {lat})"


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[VolunteerResponse])
async def get_volunteers(
    is_available: Optional[bool] = Query(None),
    skill: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """List all volunteers, filterable by availability and skills."""
    query = db.query(Volunteer)
    if is_available is not None:
        query = query.filter(Volunteer.is_available == is_available)
    if skill:
        query = query.filter(Volunteer.skills.contains([skill.lower().strip()]))
    return query.order_by(Volunteer.created_at.desc()).all()


@router.get("/{id}", response_model=VolunteerResponse)
async def get_volunteer(id: str, db: Session = Depends(get_db)):
    """Single volunteer detail."""
    vol = db.query(Volunteer).filter(Volunteer.id == id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    return vol


@router.get("/{id}/profile")
async def get_volunteer_profile(id: str, db: Session = Depends(get_db)):
    """
    Full volunteer profile including computed mission stats:
      - total_assignments, completed_tasks, active_assignments
      - most recent assignment (alert_id, zone_id, status, assigned_at)
      - days_since_joined (experience duration)
    """
    from models.assignment import VolunteerAssignment, AssignmentStatus
    from sqlalchemy import desc

    vol = db.query(Volunteer).filter(Volunteer.id == id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    # ── Fetch all assignments for this volunteer ──────────────────────────────
    assignments = (
        db.query(VolunteerAssignment)
        .filter(VolunteerAssignment.volunteer_id == vol.id)
        .order_by(desc(VolunteerAssignment.assigned_at))
        .all()
    )

    total = len(assignments)
    completed = sum(1 for a in assignments if a.status == AssignmentStatus.completed)
    active = sum(1 for a in assignments if a.status in (
        AssignmentStatus.assigned, AssignmentStatus.en_route, AssignmentStatus.on_site
    ))

    # ── Most recent task ─────────────────────────────────────────────────────
    recent_task = None
    if assignments:
        latest = assignments[0]
        alert = db.query(BioAlert).filter(BioAlert.id == latest.alert_id).first()
        recent_task = {
            "assignment_id": str(latest.id),
            "alert_id": str(latest.alert_id),
            "zone_id": str(alert.zone_id) if alert else None,
            "alert_type": alert.alert_type if alert else None,
            "severity": alert.severity.value if alert else None,
            "status": latest.status.value,
            "assigned_at": (latest.assigned_at.isoformat() + "Z") if latest.assigned_at else None,
        }

    # ── Experience duration & Honor Points ───────────────────────────────────
    days_since_joined = None
    if vol.created_at:
        delta = datetime.now(timezone.utc) - vol.created_at.replace(tzinfo=timezone.utc)
        days_since_joined = delta.days

    total_points = sum(getattr(a, 'points_awarded', 0) for a in assignments)
    reviews = []
    for a in assignments:
        comment = getattr(a, 'feedback_comment', None)
        if comment:
            reviews.append({
                "assignment_id": str(a.id),
                "alert_id": str(a.alert_id),
                "points": getattr(a, 'points_awarded', 0),
                "comment": comment,
                "date": (a.assigned_at.isoformat() + "Z") if a.assigned_at else None
            })

    return {
        "id": str(vol.id),
        "name": vol.name,
        "phone": vol.phone,
        "skills": vol.skills or [],
        "is_available": vol.is_available,
        "zone_id": str(vol.zone_id) if vol.zone_id else None,
        "latitude": vol.latitude,
        "longitude": vol.longitude,
        "last_seen_at": (vol.last_seen_at.isoformat() + "Z") if vol.last_seen_at else None,
        "created_at": (vol.created_at.isoformat() + "Z") if vol.created_at else None,
        "stats": {
            "total_assignments": total,
            "completed_tasks": completed,
            "active_assignments": active,
            "completion_rate": round(completed / total * 100) if total > 0 else 0,
            "days_since_joined": days_since_joined,
            "total_points": total_points,
        },
        "recent_task": recent_task,
        "reviews": reviews,
    }


@router.post("/", response_model=VolunteerResponse, status_code=201)
async def create_volunteer(vol_in: VolunteerCreate, db: Session = Depends(get_db)):
    """
    Register a new volunteer. If latitude and longitude are provided,
    constructs the PostGIS POINT and stores both the geographic column
    and the readable float columns.
    """
    point_wkt = None
    if vol_in.latitude is not None and vol_in.longitude is not None:
        point_wkt = _build_point_wkt(vol_in.latitude, vol_in.longitude)

    volunteer = Volunteer(
        name=vol_in.name,
        phone=vol_in.phone,
        skills=vol_in.skills,
        is_available=vol_in.is_available,
        zone_id=vol_in.zone_id,
        latitude=vol_in.latitude,
        longitude=vol_in.longitude,
        current_location=point_wkt,
        last_seen_at=datetime.now(timezone.utc) if point_wkt else None,
    )
    db.add(volunteer)
    db.commit()
    db.refresh(volunteer)

    audit = AuditLog(
        action="volunteer_registered",
        entity_type="Volunteer",
        entity_id=volunteer.id,
        payload={"name": volunteer.name, "skills": volunteer.skills},
        performed_by="API_User",
    )
    db.add(audit)
    db.commit()

    return volunteer


@router.put("/{id}/location", response_model=VolunteerResponse)
async def update_volunteer_location(
    id: str, payload: LocationUpdate, db: Session = Depends(get_db)
):
    """
    Update a volunteer's GPS coordinates. Syncs both the PostGIS POINT
    and the human-readable latitude/longitude float columns.
    """
    vol = db.query(Volunteer).filter(Volunteer.id == id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    vol.latitude = payload.latitude
    vol.longitude = payload.longitude
    vol.current_location = _build_point_wkt(payload.latitude, payload.longitude)
    vol.last_seen_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(vol)
    return vol


@router.patch("/{id}/availability", response_model=VolunteerResponse)
async def update_availability(
    id: str, payload: VolunteerAvailabilityUpdate, db: Session = Depends(get_db)
):
    """Toggle is_available and write an audit entry."""
    vol = db.query(Volunteer).filter(Volunteer.id == id).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    old_status = vol.is_available
    vol.is_available = payload.is_available

    audit = AuditLog(
        action="volunteer_availability_update",
        entity_type="Volunteer",
        entity_id=vol.id,
        payload={"old": old_status, "new": payload.is_available},
        performed_by="API_User",
    )
    db.add(audit)
    db.commit()
    db.refresh(vol)
    return vol


@router.get("/match/{alert_id}")
async def match_volunteers_for_alert(
    alert_id: str, limit: int = Query(5, ge=1, le=20), db: Session = Depends(get_db)
):
    """
    Runs the skill + proximity matching engine against an alert.
    Returns the top `limit` available volunteers ranked by:
      70% skill fit + 30% geographic proximity (PostGIS ST_Distance).
    """
    alert = db.query(BioAlert).filter(BioAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    matches = find_matched_volunteers(db, alert, limit=limit)

    return {
        "alert_id": str(alert_id),
        "required_skills": alert.recommended_skills or [],
        "total_candidates": len(matches),
        "matches": matches,
    }


@router.post("/seed", status_code=201)
async def seed_demo_volunteers(db: Session = Depends(get_db)):
    """
    Seeds 10 realistic demo volunteers across Delhi NCR with varied skills
    and GPS coordinates for testing the matching engine.
    Only runs if fewer than 5 volunteers exist.
    """
    count = db.query(Volunteer).count()
    if count >= 5:
        return {"message": f"Skipped — {count} volunteers already exist"}

    demo_volunteers = [
        {"name": "Priya Sharma",    "phone": "+91-9876543210", "lat": 28.5355, "lon": 77.3910, "skills": ["medical", "counseling"]},
        {"name": "Rahul Verma",     "phone": "+91-9812345678", "lat": 28.6280, "lon": 77.2190, "skills": ["sanitation", "water_supply", "logistics"]},
        {"name": "Anita Singh",     "phone": "+91-9988776655", "lat": 28.4595, "lon": 77.0266, "skills": ["medical", "food_distribution"]},
        {"name": "Kiran Gupta",     "phone": "+91-9090909090", "lat": 28.7041, "lon": 77.1025, "skills": ["education", "communication"]},
        {"name": "Mohammad Iqbal",  "phone": "+91-8877665544", "lat": 28.6517, "lon": 77.2219, "skills": ["rescue", "logistics", "sanitation"]},
        {"name": "Sunita Devi",     "phone": "+91-7766554433", "lat": 28.5245, "lon": 77.1855, "skills": ["medical", "sanitation", "counseling"]},
        {"name": "Arun Patel",      "phone": "+91-6655443322", "lat": 28.6692, "lon": 77.4538, "skills": ["water_supply", "food_distribution"]},
        {"name": "Meera Joshi",     "phone": "+91-9999888877", "lat": 28.4089, "lon": 77.3178, "skills": ["medical", "education", "communication"]},
        {"name": "Deepak Tiwari",   "phone": "+91-8888777766", "lat": 28.5921, "lon": 77.0460, "skills": ["rescue", "logistics"]},
        {"name": "Pooja Nair",      "phone": "+91-7777666655", "lat": 28.6350, "lon": 77.2800, "skills": ["medical", "food_distribution", "sanitation"]},
    ]

    created = []
    for v in demo_volunteers:
        point_wkt = _build_point_wkt(v["lat"], v["lon"])
        volunteer = Volunteer(
            name=v["name"],
            phone=v["phone"],
            skills=v["skills"],
            is_available=True,
            latitude=v["lat"],
            longitude=v["lon"],
            current_location=point_wkt,
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(volunteer)
        created.append(v["name"])

    db.commit()
    logger.info(f"Seeded {len(created)} demo volunteers")
    return {"message": f"Seeded {len(created)} volunteers", "names": created}
