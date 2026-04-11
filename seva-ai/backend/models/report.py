from sqlalchemy import Column, String, DateTime, Enum, Text, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
from database.connection import Base
from sqlalchemy.sql import func
import uuid
import enum

class SourceType(str, enum.Enum):
    voice = 'voice'
    paper = 'paper'
    whatsapp = 'whatsapp'
    manual = 'manual'

class UrgencyLevel(str, enum.Enum):
    low = 'low'
    medium = 'medium'
    high = 'high'
    critical = 'critical'

class FieldReport(Base):
    __tablename__ = "field_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id = Column(UUID(as_uuid=True), ForeignKey('zones.id'), index=True, nullable=True)
    source_type = Column(Enum(SourceType, name="source_type_enum"), nullable=False)
    raw_text = Column(Text, nullable=True)
    extracted_need = Column(String, nullable=True)
    extracted_location = Column(String, nullable=True)
    urgency_level = Column(Enum(UrgencyLevel, name="urgency_level_enum"), nullable=False)
    bio_markers_detected = Column(JSONB, nullable=True)
    coordinates = Column(Geometry('POINT', spatial_index=True), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    coordinator_name = Column(String, nullable=True)
    reported_at = Column(DateTime, default=func.now(), index=True)
    created_at = Column(DateTime, default=func.now())
