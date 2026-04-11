from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from models.zone import RiskLevel

class ZoneResponse(BaseModel):
    """Schema for Zone response, includes calculated metrics."""
    id: UUID
    name: str
    city: str
    bio_risk_index: float
    risk_level: RiskLevel
    report_count: int = 0
    boundary_geojson: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
