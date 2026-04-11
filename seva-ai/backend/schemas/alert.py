from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from models.alert import AlertSeverity

class AlertCreate(BaseModel):
    """Schema for triggering a new BioAlert."""
    zone_id: UUID
    alert_type: str
    triggered_by_reports: Optional[Any] = None
    severity: AlertSeverity
    is_active: bool = True
    recommended_skills: List[str] = []

class AlertResponse(AlertCreate):
    """Schema for returning a BioAlert."""
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
