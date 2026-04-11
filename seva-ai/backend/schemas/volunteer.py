from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime

ALLOWED_SKILLS = {
    "medical", "sanitation", "food_distribution", "education",
    "logistics", "water_supply", "rescue", "counseling", "communication"
}

class VolunteerCreate(BaseModel):
    """Schema for registering a new volunteer."""
    name: str
    phone: str
    skills: List[str] = []
    is_available: bool = True
    zone_id: Optional[UUID] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator('skills')
    @classmethod
    def validate_skills(cls, v: List[str]) -> List[str]:
        # Lowercase and deduplicate; unknown skills are allowed but normalised
        return list({s.lower().strip() for s in v})

class LocationUpdate(BaseModel):
    """Schema for updating a volunteer's GPS coordinates."""
    latitude: float
    longitude: float

class VolunteerAvailabilityUpdate(BaseModel):
    """Schema for toggling deployment status."""
    is_available: bool

class VolunteerResponse(BaseModel):
    """Full volunteer detail including location fields."""
    id: UUID
    name: str
    phone: str
    skills: List[str]
    is_available: bool
    zone_id: Optional[UUID] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    last_seen_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
