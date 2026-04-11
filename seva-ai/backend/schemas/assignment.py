from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime
from models.assignment import AssignmentStatus

class AssignmentCreate(BaseModel):
    """Schema for creating a volunteer assignment."""
    alert_id: UUID
    volunteer_id: UUID
    notes: Optional[str] = None
    status: AssignmentStatus = AssignmentStatus.assigned

class AssignmentResponse(AssignmentCreate):
    """Schema for Assignment response."""
    id: UUID
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)
