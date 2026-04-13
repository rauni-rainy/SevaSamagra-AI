from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
import requests
import logging

logger = logging.getLogger(__name__)

from database.connection import get_db
from models.report import FieldReport, SourceType, UrgencyLevel
from models.audit_log import AuditLog
from schemas.report import ReportResponse, ReportCreate, ReportListResponse, ManualReportEntry, PaginatedReports
from services.zone_risk_service import update_zone_bio_risk
from services.ner_extractor import extract_need_info
from services.gemini_ner import extract_with_gemini
from websocket.socket_manager import socket_manager
from models.zone import Zone
from pydantic import BaseModel

class SimulateVoiceRequest(BaseModel):
    text: str

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("", response_model=PaginatedReports)
async def get_reports(
    zone_id: Optional[str] = Query(None),
    urgency_level: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Paginated, filterable Retrieve all field reports.
    """
    query = db.query(FieldReport)
    
    if zone_id:
        query = query.filter(FieldReport.zone_id == zone_id)
    if urgency_level:
        query = query.filter(FieldReport.urgency_level == urgency_level)
    if source_type:
        query = query.filter(FieldReport.source_type == source_type)
    if start_date:
        query = query.filter(FieldReport.reported_at >= start_date)
    if end_date:
        query = query.filter(FieldReport.reported_at <= end_date)
        
    total = query.count()
    
    reports = query.order_by(desc(FieldReport.reported_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": reports
    }

@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, db: Session = Depends(get_db)):
    """
    Single report with all fields.
    """
    report = db.query(FieldReport).filter(FieldReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.post("", response_model=ReportResponse)
async def create_report(report_in: ReportCreate, db: Session = Depends(get_db)):
    """
    Manual report creation (e.g. for paper/WhatsApp input).
    Updates bio risk, emits realtime event, registers audit.
    """
    report = FieldReport(
        zone_id=report_in.zone_id,
        source_type=report_in.source_type,
        raw_text=report_in.raw_text,
        extracted_need=report_in.extracted_need,
        extracted_location=report_in.extracted_location,
        urgency_level=report_in.urgency_level,
        bio_markers_detected=report_in.bio_markers_detected,
        latitude=report_in.latitude,
        longitude=report_in.longitude,
        coordinator_name=report_in.coordinator_name,
        coordinates=f"SRID=4326;POINT({report_in.longitude} {report_in.latitude})" if report_in.longitude and report_in.latitude else None
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)
    
    # Call update_zone_bio_risk if bio_markers found and zone is populated
    if report.zone_id and report.bio_markers_detected:
        update_zone_bio_risk(db, report.zone_id, report.bio_markers_detected)
        
    # Write AuditLog
    audit = AuditLog(
        action="manual_report_created",
        entity_type="FieldReport",
        entity_id=report.id,
        payload={"source": report.source_type.value},
        performed_by="API_User_Manual"
    )
    db.add(audit)
    db.commit()

    # Emit realtime event
    report_dict = {
        "id": str(report.id),
        "zone_id": str(report.zone_id) if report.zone_id else None,
        "extracted_need": report.extracted_need,
        "urgency_level": report.urgency_level.value,
        "source_type": report.source_type.value,
        "bio_markers_detected": report.bio_markers_detected,
        "reported_at": (report.reported_at.isoformat() + "Z") if report.reported_at else None,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "coordinator_name": report.coordinator_name
    }
    
    await socket_manager.emit_new_report(report_dict)

    return report

@router.post("/simulate/voice", response_model=ReportResponse)
async def simulate_voice_report(req: SimulateVoiceRequest, db: Session = Depends(get_db)):
    """
    Simulates the voice pipeline by taking plain text, running Gemini AI NER extraction
    (location, urgency, bio-markers, need summary in one call), forward-geocoding the
    extracted location to lat/lon, and persisting the report.
    Falls back to legacy regex NER if Gemini is unavailable.
    """
    text = req.text
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    # --- Gemini AI NER (single prompt: location + urgency + biomarkers + geocoords) ---
    extracted_data = extract_with_gemini(text)

    try:
        urgency_level = UrgencyLevel(extracted_data["urgency_level"])
    except ValueError:
        urgency_level = UrgencyLevel.medium

    lat = extracted_data.get("latitude")
    lon = extracted_data.get("longitude")
    point_str = None

    zone_id = None
    if lat is not None and lon is not None:
        point_str = f"SRID=4326;POINT({lon} {lat})"
        from sqlalchemy import func
        point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        zone = db.query(Zone).filter(func.ST_Intersects(Zone.boundary, point)).first()
        if not zone:
            zone = db.query(Zone).order_by(func.ST_Distance(Zone.boundary, point)).first()
        if zone:
            zone_id = zone.id
    
    if not zone_id:
        zone = db.query(Zone).first() 
        zone_id = zone.id if zone else None

    report = FieldReport(
        zone_id=zone_id,
        source_type=SourceType.voice,
        raw_text=text,
        extracted_need=extracted_data["extracted_need"],
        extracted_location=extracted_data["extracted_location"],
        urgency_level=urgency_level,
        bio_markers_detected=extracted_data["bio_markers_detected"],
        latitude=lat,
        longitude=lon,
        coordinates=point_str,
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    if zone_id and extracted_data["bio_markers_detected"]:
        update_zone_bio_risk(db, zone_id, extracted_data["bio_markers_detected"])

    audit = AuditLog(
        action="simulate_voice_report",
        entity_type="FieldReport",
        entity_id=report.id,
        payload={"text": text, "gemini_location": extracted_data["extracted_location"]},
        performed_by="API_Demo"
    )
    db.add(audit)
    db.commit()

    report_dict = {
        "id": str(report.id),
        "zone_id": str(report.zone_id) if report.zone_id else None,
        "extracted_need": report.extracted_need,
        "extracted_location": report.extracted_location,
        "urgency_level": report.urgency_level.value,
        "source_type": report.source_type.value,
        "bio_markers_detected": report.bio_markers_detected,
        "reported_at": (report.reported_at.isoformat() + "Z") if report.reported_at else None,
        "latitude": report.latitude,
        "longitude": report.longitude,
    }

    await socket_manager.emit_new_report(report_dict)

    return report

@router.post("/manual-entry", response_model=ReportResponse)
async def create_manual_report_entry(req: ManualReportEntry, db: Session = Depends(get_db)):
    """
    Manual report creation via raw text (coordinators pasting WhatsApp messages).
    Runs NER payload extraction, attaches real GPS and coordinator names.
    """
    text = req.text
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
        
    extracted_data = extract_need_info(text)
    
    try:
        urgency_level = UrgencyLevel(extracted_data["urgency_level"])
    except ValueError:
        urgency_level = UrgencyLevel.medium

    point_str = None
    zone_id = None
    
    if req.latitude is not None and req.longitude is not None:
        point_str = f"SRID=4326;POINT({req.longitude} {req.latitude})"
        from sqlalchemy import func
        point = func.ST_SetSRID(func.ST_MakePoint(req.longitude, req.latitude), 4326)
        zone = db.query(Zone).filter(func.ST_Intersects(Zone.boundary, point)).first()
        if not zone:
            zone = db.query(Zone).order_by(func.ST_Distance(Zone.boundary, point)).first()
        if zone:
            zone_id = zone.id
    
    if not zone_id:
        zone = db.query(Zone).first()
        zone_id = zone.id if zone else None

    if req.latitude is not None and req.longitude is not None:
        
        # Reverse Geocode attempt
        resolved_location = None
        try:
            headers = {"User-Agent": "SevaAI-Platform/1.0"}
            res = requests.get(
                f"https://nominatim.openstreetmap.org/reverse?format=json&lat={req.latitude}&lon={req.longitude}",
                headers=headers,
                timeout=5
            )
            if res.status_code == 200:
                addr = res.json().get("address", {})
                parts = []
                if "suburb" in addr: parts.append(addr["suburb"])
                elif "neighbourhood" in addr: parts.append(addr["neighbourhood"])
                elif "road" in addr: parts.append(addr["road"])
                
                city = addr.get("city") or addr.get("town") or addr.get("village")
                if city: parts.append(city)
                
                if parts:
                    resolved_location = ", ".join(parts)
                else:
                    resolved_location = res.json().get("display_name", "").split(",")[0]
        except Exception as e:
            logger.error(f"Reverse geocode error: {e}")

        # Override location if valid coordinates gave us a real place, else fallback to AI or default
        if resolved_location:
            extracted_data["extracted_location"] = resolved_location
        elif extracted_data["extracted_location"] == "Unknown":
            extracted_data["extracted_location"] = "GPS Verified Coordinates"

    report = FieldReport(
        zone_id=zone_id,
        source_type=SourceType.manual,
        raw_text=text,
        extracted_need=extracted_data["extracted_need"],
        extracted_location=extracted_data["extracted_location"],
        urgency_level=urgency_level,
        bio_markers_detected=extracted_data["bio_markers_detected"],
        latitude=req.latitude,
        longitude=req.longitude,
        coordinator_name=req.coordinator_name or "Unknown Coordinator",
        coordinates=point_str
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)
    
    if zone_id and extracted_data["bio_markers_detected"]:
        update_zone_bio_risk(db, zone_id, extracted_data["bio_markers_detected"])
        
    audit = AuditLog(
        action="manual_text_report",
        entity_type="FieldReport",
        entity_id=report.id,
        payload={"text": text, "coordinator": req.coordinator_name},
        performed_by=f"Coordinator_{req.coordinator_name}" if req.coordinator_name else "API_User_Manual"
    )
    db.add(audit)
    db.commit()

    report_dict = {
        "id": str(report.id),
        "zone_id": str(report.zone_id) if report.zone_id else None,
        "extracted_need": report.extracted_need,
        "urgency_level": report.urgency_level.value,
        "source_type": report.source_type.value,
        "bio_markers_detected": report.bio_markers_detected,
        "reported_at": (report.reported_at.isoformat() + "Z") if report.reported_at else None,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "coordinator_name": report.coordinator_name
    }
    
    await socket_manager.emit_new_report(report_dict)

    return report
