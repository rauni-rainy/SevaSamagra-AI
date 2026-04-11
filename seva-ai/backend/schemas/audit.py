from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from uuid import UUID
from datetime import datetime

class AuditLogResponse(BaseModel):
    """Schema for displaying audit log entries."""
    id: UUID
    action: str
    entity_type: str
    entity_id: UUID
    payload: Optional[Any] = None
    performed_by: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class PaginatedAuditLogs(BaseModel):
    total: int
    page: int
    page_size: int
    data: list[AuditLogResponse]
