"""
matching_engine.py — Seva AI Volunteer Skill & Proximity Matching Engine

Algorithm:
  1. Filter volunteers where is_available = True and they have at least 1 GPS coordinate
  2. Compute distance_km via PostGIS ST_Distance(Geography) in the DB query itself
     (avoids loading all volunteers into Python for math)
  3. Compute skill_match_score = |skills ∩ required| / |required|     (0.0 – 1.0)
  4. Compute proximity_score   = 1 / (1 + distance_km)                (0.0 – 1.0)
  5. final_score = 0.7 × skill_match_score + 0.3 × proximity_score

Weights: 70% skill fit, 30% geographic proximity (PostGIS Geography haversine distance)

Returns: sorted list of dicts (top `limit`, descending by final_score)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, case, literal
from geoalchemy2.functions import ST_Distance, ST_MakePoint, ST_SetSRID
from geoalchemy2.types import Geography
from sqlalchemy import cast
from models.alert import BioAlert
from models.zone import Zone
from models.volunteer import Volunteer

logger = logging.getLogger(__name__)

SKILL_WEIGHT = 0.70
PROXIMITY_WEIGHT = 0.30


def _get_alert_reference_point(db: Session, alert: BioAlert):
    """
    Returns a WKB geography point representing the alert's geographic origin.

    Priority order:
      1. Zone boundary centroid (most accurate — actual polygon centroid)
      2. Zone lat/lon if available on the zone record
      3. None (matching engine will skip proximity scoring)
    """
    if not alert.zone_id:
        return None

    zone: Zone = db.query(Zone).filter(Zone.id == alert.zone_id).first()
    if zone is None:
        return None

    if zone.boundary is not None:
        # ST_Centroid on the polygon gives us the exact geographic centre
        return func.ST_Centroid(zone.boundary)

    return None


def find_matched_volunteers(db: Session, alert: BioAlert, limit: int = 5) -> list[dict]:
    """
    Core matching function. Returns a ranked list of volunteer match objects.

    Each result dict:
    {
        "volunteer": { id, name, phone, skills, is_available, zone_id, latitude, longitude },
        "skill_match_score": float,   # 0.0 – 1.0
        "proximity_km":      float,   # straight-line distance via PostGIS
        "final_score":       float,   # weighted composite (0.0 – 1.0)
        "matched_skills":    [str],   # skills volunteer has that alert needs
        "missing_skills":    [str],   # skills alert needs that volunteer lacks
    }
    """
    required_skills: set[str] = set(alert.recommended_skills or [])
    n_required = len(required_skills) if required_skills else 1

    # ── Reference point for proximity calculation ─────────────────────────────
    ref_point = _get_alert_reference_point(db, alert)

    # ── Build DB query ────────────────────────────────────────────────────────
    # We compute distance in the database to let PostGIS do the heavy lifting
    if ref_point is not None:
        # Cast both geometries to Geography to get meters (great-circle distance)
        distance_m = ST_Distance(
            cast(Volunteer.current_location, Geography),
            cast(ref_point, Geography),
        )
        distance_km_expr = distance_m / 1000.0

        rows = (
            db.query(Volunteer, distance_km_expr.label("distance_km"))
            .filter(
                Volunteer.is_available == True,           # noqa: E712
                Volunteer.current_location.isnot(None),   # must have GPS
            )
            .all()
        )
        # Also fetch volunteers WITHOUT a location (they'll get a penalty distance)
        no_loc_rows = (
            db.query(Volunteer)
            .filter(
                Volunteer.is_available == True,           # noqa: E712
                Volunteer.current_location.is_(None),
            )
            .all()
        )
        # Give no-location volunteers a 25 km penalty distance
        rows = list(rows) + [(v, 25.0) for v in no_loc_rows]

    else:
        # No zone reference — fetch all available volunteers, use 10 km flat distance
        all_vols = db.query(Volunteer).filter(Volunteer.is_available == True).all()  # noqa: E712
        rows = [(v, 10.0) for v in all_vols]

    # ── Score each volunteer ──────────────────────────────────────────────────
    ranked: list[dict] = []

    for row in rows:
        volunteer: Volunteer = row[0]
        raw_distance = row[1]

        # Safely convert distance (may be a SQLAlchemy Decimal or None)
        try:
            distance_km = float(raw_distance) if raw_distance is not None else 25.0
        except (TypeError, ValueError):
            distance_km = 25.0

        # Skill scoring
        vol_skills = set(volunteer.skills or [])
        matched = vol_skills & required_skills
        missing = required_skills - vol_skills

        if required_skills:
            skill_match_score = len(matched) / n_required
        else:
            skill_match_score = 1.0  # No specific skills required → everyone qualifies

        # Proximity scoring: decays rapidly with distance
        # At 0 km → 1.0, at 1 km → 0.5, at 5 km → 0.167, at 10 km → 0.091
        proximity_score = 1.0 / (1.0 + distance_km)

        final_score = (skill_match_score * SKILL_WEIGHT) + (proximity_score * PROXIMITY_WEIGHT)

        ranked.append({
            "volunteer": {
                "id": str(volunteer.id),
                "name": volunteer.name,
                "phone": volunteer.phone,
                "skills": volunteer.skills or [],
                "is_available": volunteer.is_available,
                "zone_id": str(volunteer.zone_id) if volunteer.zone_id else None,
                "latitude": volunteer.latitude,
                "longitude": volunteer.longitude,
            },
            "skill_match_score": round(skill_match_score, 3),
            "proximity_km": round(distance_km, 2),
            "final_score": round(final_score, 4),
            "matched_skills": sorted(matched),
            "missing_skills": sorted(missing),
        })

    # ── Sort descending by final_score, return top `limit` ───────────────────
    ranked.sort(key=lambda x: x["final_score"], reverse=True)

    logger.info(
        f"Matching engine: alert={alert.id} | candidates={len(ranked)} | "
        f"returning top {min(limit, len(ranked))}"
    )

    return ranked[:limit]
