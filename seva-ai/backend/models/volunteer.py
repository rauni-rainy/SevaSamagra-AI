from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from geoalchemy2 import Geometry
from database.connection import Base
from sqlalchemy.sql import func
import uuid

class Volunteer(Base):
    __tablename__ = "volunteers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    skills = Column(ARRAY(String), default=[])
    current_location = Column(Geometry('POINT', srid=4326, spatial_index=True), nullable=True)
    latitude = Column(Float, nullable=True)   # readable snapshot of current_location
    longitude = Column(Float, nullable=True)  # readable snapshot of current_location
    is_available = Column(Boolean, default=True, index=True)
    zone_id = Column(UUID(as_uuid=True), ForeignKey('zones.id'), index=True, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)  # when GPS was last refreshed
    created_at = Column(DateTime, default=func.now())
