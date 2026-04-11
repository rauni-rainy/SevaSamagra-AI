from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from database.connection import Base
from sqlalchemy.sql import func
import uuid
import enum

class AlertSeverity(str, enum.Enum):
    watch = 'watch'
    warning = 'warning'
    critical = 'critical'

class BioAlert(Base):
    __tablename__ = "bio_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id = Column(UUID(as_uuid=True), ForeignKey('zones.id'), index=True, nullable=False)
    alert_type = Column(String, nullable=False)
    triggered_by_reports = Column(JSONB, nullable=True)
    severity = Column(Enum(AlertSeverity, name="alert_severity_enum"), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    recommended_skills = Column(ARRAY(String), default=[])
    created_at = Column(DateTime, default=func.now())
