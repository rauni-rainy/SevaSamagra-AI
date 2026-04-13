import logging
from fastapi import APIRouter, Request, Response, Depends
from sqlalchemy.orm import Session
from database.connection import get_db
from models.report import FieldReport, SourceType, UrgencyLevel
from models.audit_log import AuditLog
from models.zone import Zone
from services.transcription import transcribe_audio
from services.gemini_ner import extract_with_gemini
from services.zone_risk_service import update_zone_bio_risk
from websocket.socket_manager import socket_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice Webhooks"])

# Simple in-memory cache for idempotency check on Twilio retries
processed_recording_urls = set()

@router.get("")
async def get_voice_status():
    """
    Status of the Voice / IVR pipeline.
    """
    return {"status": "ok"}

@router.post("/incoming")
async def handle_incoming_call():
    """
    Twilio webhook endpoint for incoming calls. Returns TwiML prompting the 
    user to leave a recorded message.
    """
    twiml = '''<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say language="hi-IN">Namaste. SEVA AI mein aapka swagat hai. Apni samasya bolein.</Say>
        <Say>Please describe your community need after the beep.</Say>
        <Record maxLength="60" action="/api/voice/recording" method="POST" playBeep="true"/>
    </Response>'''
    
    return Response(content=twiml, media_type="application/xml")

@router.post("/recording")
async def handle_recording(request: Request, db: Session = Depends(get_db)):
    """
    Twilio webhook endpoint called when the audio recording is finished.
    Downloads the audio, transcodes, applies NER, updates bio risk, and creates a report.
    """
    form_data = await request.form()
    recording_url = form_data.get("RecordingUrl")
    
    if not recording_url:
        logger.error("No RecordingUrl found in Twilio request.")
        return Response(content='<Response><Say>Error processing recording.</Say></Response>', media_type="application/xml")

    # Idempotency check
    if recording_url in processed_recording_urls:
        logger.info(f"Idempotency hit for {recording_url}. Ignoring duplicate.")
        return Response(content='<Response><Say>Shukriya.</Say></Response>', media_type="application/xml")
        
    processed_recording_urls.add(recording_url)

    # 1. Transcribe
    transcript = transcribe_audio(recording_url)
    
    if not transcript:
        logger.error("Transcription resulted in empty text.")
        return Response(content='<Response><Say>Transcription failed.</Say></Response>', media_type="application/xml")
        
    # 2. Extract NER Need Info (using Gemini AI)
    extracted_data = extract_with_gemini(transcript)
    
    # 3. Determine Enum values
    try:
        urgency_level = UrgencyLevel(extracted_data["urgency_level"])
    except ValueError:
        urgency_level = UrgencyLevel.medium

    # 4. Spatial Zone Mapping
    zone_id = None
    lat = extracted_data.get("latitude")
    lon = extracted_data.get("longitude")
    point_str = None
    
    if lat is not None and lon is not None:
        point_str = f"SRID=4326;POINT({lon} {lat})"
        from sqlalchemy import func
        point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        # Find zone intersecting this point
        zone = db.query(Zone).filter(func.ST_Intersects(Zone.boundary, point)).first()
        if not zone:
            # Fallback to nearest zone
            zone = db.query(Zone).order_by(func.ST_Distance(Zone.boundary, point)).first()
        if zone:
            zone_id = zone.id
    
    if not zone_id:
        zone = db.query(Zone).first()  # Fallback to first configured zone
        zone_id = zone.id if zone else None

    # 5. Create Field Report
    field_report = FieldReport(
        zone_id=zone_id,
        source_type=SourceType.voice,
        raw_text=transcript,
        extracted_need=extracted_data["extracted_need"],
        extracted_location=extracted_data["extracted_location"],
        urgency_level=urgency_level,
        bio_markers_detected=extracted_data["bio_markers_detected"],
        latitude=lat,
        longitude=lon,
        coordinates=point_str
    )
    db.add(field_report)
    db.commit()
    db.refresh(field_report)
    
    # 4. Update Bio Risk
    if zone_id and extracted_data["bio_markers_detected"]:
        update_zone_bio_risk(db, zone_id, extracted_data["bio_markers_detected"])

    # 5. Audit Log
    audit = AuditLog(
        action="voice_report_created",
        entity_type="FieldReport",
        entity_id=field_report.id,
        payload={"recording_url": recording_url, "extracted_keys": list(extracted_data.keys())},
        performed_by="Twilio"
    )
    db.add(audit)
    db.commit()

    # 6. Emit WS Event
    report_dict = {
        "id": str(field_report.id),
        "source_type": field_report.source_type.value,
        "extracted_need": field_report.extracted_need,
        "urgency_level": field_report.urgency_level.value,
        "zone_id": str(field_report.zone_id) if field_report.zone_id else None
    }
    await socket_manager.emit_new_report(report_dict)

    # 7. Respond with TwiML
    twiml = '''<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>Shukriya. Aapki report darj ho gayi hai. Dhanyawad.</Say>
    </Response>'''
    return Response(content=twiml, media_type="application/xml")

@router.get("/test")
async def test_voice_pipeline(text: str, db: Session = Depends(get_db)):
    """
    Demo/Test endpoint that bypasses Twilio. 
    It runs the extraction pipeline on the provided text, writes to DB,
    and returns the created report as JSON.
    """
    if not text:
        return {"error": "Provide 'text' parameter."}

    extracted_data = extract_with_gemini(text)
    
    try:
        urgency_level = UrgencyLevel(extracted_data["urgency_level"])
    except ValueError:
        urgency_level = UrgencyLevel.medium

    zone_id = None
    lat = extracted_data.get("latitude")
    lon = extracted_data.get("longitude")
    point_str = None
    
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

    field_report = FieldReport(
        zone_id=zone_id,
        source_type=SourceType.voice,
        raw_text=text,
        extracted_need=extracted_data["extracted_need"],
        extracted_location=extracted_data["extracted_location"],
        urgency_level=urgency_level,
        bio_markers_detected=extracted_data["bio_markers_detected"],
        latitude=lat,
        longitude=lon,
        coordinates=point_str
    )
    db.add(field_report)
    db.commit()
    db.refresh(field_report)
    
    if zone_id and extracted_data["bio_markers_detected"]:
        update_zone_bio_risk(db, zone_id, extracted_data["bio_markers_detected"])

    # Audit Log
    audit = AuditLog(
        action="test_voice_report_created",
        entity_type="FieldReport",
        entity_id=field_report.id,
        payload={"text": text},
        performed_by="DemoTestEndpoint"
    )
    db.add(audit)
    db.commit()

    # Emit WS Event
    report_dict = {
        "id": str(field_report.id),
        "source_type": field_report.source_type.value,
        "extracted_need": field_report.extracted_need,
        "urgency_level": field_report.urgency_level.value,
        "zone_id": str(field_report.zone_id) if field_report.zone_id else None
    }
    await socket_manager.emit_new_report(report_dict)

    return {"message": "Test successful", "report": report_dict}
