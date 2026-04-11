from sqlalchemy.orm import Session
from models.zone import Zone, RiskLevel
from models.alert import BioAlert, AlertSeverity
from models.audit_log import AuditLog
import asyncio

def update_zone_bio_risk(db: Session, zone_id, bio_markers: list) -> Zone:
    """
    Updates the biological risk index of a given zone based on newly detected bio-markers.
    
    If the index crosses predefined thresholds, it upgrades the zone's risk level
    and automatically issues a new BioAlert. An AuditLog entry is recorded for the change.
    
    Args:
        db (Session): SQLAlchemy database session.
        zone_id (UUID): The ID of the zone to update.
        bio_markers (list): A list of unique bio-marker categories detected.
        
    Returns:
        Zone: The updated Zone object.
    """
    if not zone_id:
        return None
        
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        return None

    # Each unique bio_marker category adds 1.0 to bio_risk_index
    unique_markers = list(set(bio_markers))
    increase_amount = float(len(unique_markers))
    
    if increase_amount == 0.0:
        return zone # No risk to add
        
    old_index = zone.bio_risk_index
    zone.bio_risk_index += increase_amount
    old_risk_level = zone.risk_level

    # Check thresholds for amber and red
    new_risk_level = old_risk_level
    if zone.bio_risk_index > 5.0:
        new_risk_level = RiskLevel.red
    elif zone.bio_risk_index > 2.0:
        if new_risk_level != RiskLevel.red:
            new_risk_level = RiskLevel.amber

    threshold_crossed = (new_risk_level != old_risk_level)
    zone.risk_level = new_risk_level

    db.add(zone)
    db.commit()
    db.refresh(zone)

    if threshold_crossed:
        severity = AlertSeverity.warning if new_risk_level == RiskLevel.amber else AlertSeverity.critical
        alert = BioAlert(
            zone_id=zone.id,
            alert_type="Threshold Crossed",
            triggered_by_reports=unique_markers,
            severity=severity,
            recommended_skills=['medical', 'sanitation']
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        # Emit realtime events (fire and forget — zone_risk_service is sync, scheduler is async)
        from websocket.socket_manager import socket_manager
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(socket_manager.emit_new_alert({
                    "id": str(alert.id),
                    "zone_id": str(alert.zone_id),
                    "alert_type": alert.alert_type,
                    "severity": alert.severity.value,
                    "is_active": alert.is_active,
                    "recommended_skills": alert.recommended_skills,
                    "triggered_by_reports": alert.triggered_by_reports,
                    "created_at": alert.created_at.isoformat() + "Z" if alert.created_at else None,
                }))
                asyncio.ensure_future(socket_manager.emit_zone_update({
                    "id": str(zone.id),
                    "bio_risk_index": zone.bio_risk_index,
                    "risk_level": zone.risk_level.value,
                }))
        except RuntimeError:
            pass  # No event loop — background task context

    audit_entry = AuditLog(
        action="update_zone_bio_risk",
        entity_type="Zone",
        entity_id=zone.id,
        payload={"old_index": old_index, "new_index": zone.bio_risk_index, "markers_added": unique_markers, "threshold_crossed": threshold_crossed},
        performed_by="system-voice-pipeline"
    )
    db.add(audit_entry)
    db.commit()

    return zone
