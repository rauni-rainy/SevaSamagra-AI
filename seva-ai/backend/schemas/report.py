from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from models.report import SourceType, UrgencyLevel

class ReportCreate(BaseModel):
    """Schema for creating a new Field Report."""
    zone_id: Optional[UUID] = None
    source_type: SourceType
    raw_text: Optional[str] = None
    extracted_need: Optional[str] = None
    extracted_location: Optional[str] = None
    urgency_level: UrgencyLevel
    bio_markers_detected: Optional[Any] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinator_name: Optional[str] = None

class ManualReportEntry(BaseModel):
    """Schema for manual entry from field coordinators."""
    text: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinator_name: Optional[str] = None

class ReportResponse(ReportCreate):
    """Schema for returning a Field Report."""
    id: UUID
    reported_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReportListResponse(BaseModel):
    """Schema for a list of Field Reports."""
    reports: List[ReportResponse]

class PaginatedReports(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[ReportResponse]
