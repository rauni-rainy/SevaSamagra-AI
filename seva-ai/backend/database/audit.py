from sqlalchemy.orm import Session
from models.audit_log import AuditLog

def log_action(db: Session, action: str, entity_type: str, entity_id, payload: dict = None, performed_by: str = None):
    """
    Writes a row to AuditLog automatically.
    """
    audit_entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        performed_by=performed_by
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry
