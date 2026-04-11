from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from sqlalchemy.sql import text
from typing import List, Optional
import json

from database.connection import get_db
from models.zone import Zone
from models.report import FieldReport
from models.alert import BioAlert
from schemas.zone import ZoneResponse

router = APIRouter(prefix="/zones", tags=["Zones"])

@router.get("/", response_model=List[ZoneResponse])
async def get_zones(db: Session = Depends(get_db)):
    """
    Retrieve all defined geographic zones and their calculated risk levels.
    """
    zones = db.query(Zone).all()
    result = []
    
    for zone in zones:
        # Count reports
        report_count = db.query(func.count(FieldReport.id)).filter(FieldReport.zone_id == zone.id).scalar()
        
        # Get GeoJSON boundary directly
        geojson_str = None
        if zone.boundary is not None:
            # Query db for geojson representation of this zone's geometry
            geojson_str = db.scalar(func.ST_AsGeoJSON(zone.boundary))
            
        boundary_dict = json.loads(geojson_str) if geojson_str else None
        
        # Build response
        zone_dict = {
            "id": zone.id,
            "name": zone.name,
            "city": zone.city,
            "bio_risk_index": zone.bio_risk_index,
            "risk_level": zone.risk_level,
            "report_count": report_count or 0,
            "created_at": zone.created_at,
            "updated_at": zone.updated_at,
            "boundary_geojson": boundary_dict
        }
        result.append(zone_dict)
        
    return result

@router.get("/{zone_id}")
async def get_zone_details(zone_id: str, db: Session = Depends(get_db)):
    """
    Single zone with its active alerts and last 10 reports.
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    report_count = db.query(func.count(FieldReport.id)).filter(FieldReport.zone_id == zone.id).scalar()
    
    # Active alerts
    alerts = db.query(BioAlert).filter(BioAlert.zone_id == zone_id, BioAlert.is_active == True).all()
    
    # Last 10 reports
    latest_reports = db.query(FieldReport).filter(FieldReport.zone_id == zone_id).order_by(desc(FieldReport.reported_at)).limit(10).all()

    return {
        "zone": {
            "id": zone.id,
            "name": zone.name,
            "city": zone.city,
            "bio_risk_index": zone.bio_risk_index,
            "risk_level": zone.risk_level.value,
            "report_count": report_count or 0,
            "created_at": zone.created_at,
            "updated_at": zone.updated_at
        },
        "active_alerts": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "severity": a.severity.value,
                "created_at": a.created_at
            } for a in alerts
        ],
        "latest_reports": [
            {
                "id": r.id,
                "source_type": r.source_type.value,
                "extracted_need": r.extracted_need,
                "urgency_level": r.urgency_level.value,
                "reported_at": r.reported_at
            } for r in latest_reports
        ]
    }

@router.get("/{zone_id}/reports")
async def get_zone_reports(
    zone_id: str, 
    page: int = Query(1, ge=1), 
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Paginated reports for a specific zone.
    """
    query = db.query(FieldReport).filter(FieldReport.zone_id == zone_id)
    total = query.count()
    
    reports = query.order_by(desc(FieldReport.reported_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": reports
    }
