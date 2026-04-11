from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional

from database.connection import get_db
from models.audit_log import AuditLog
from schemas.audit import AuditLogResponse, PaginatedAuditLogs

router = APIRouter(prefix="/audit", tags=["Audit"])

@router.get("/", response_model=PaginatedAuditLogs)
async def get_audit_logs(
    entity_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Paginated general audit log stream, sorting most recent first.
    """
    query = db.query(AuditLog)
    
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
        
    total = query.count()
    logs = query.order_by(desc(AuditLog.timestamp)).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": logs
    }

@router.get("/{entity_type}/{entity_id}", response_model=list[AuditLogResponse])
async def get_entity_audit_trail(entity_type: str, entity_id: str, db: Session = Depends(get_db)):
    """
    Full localized audit trail isolated strictly to one backend specific entity.
    """
    logs = db.query(AuditLog).filter(
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id
    ).order_by(desc(AuditLog.timestamp)).all()
    
    return logs
