from sqlalchemy import Column, String, Float, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
from database.connection import Base
from sqlalchemy.sql import func
import uuid
import enum

class RiskLevel(str, enum.Enum):
    green = 'green'
    amber = 'amber'
    red = 'red'

class Zone(Base):
    __tablename__ = "zones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    city = Column(String, nullable=False)
    boundary = Column(Geometry('POLYGON', spatial_index=True), nullable=True)
    bio_risk_index = Column(Float, default=0.0)
    risk_level = Column(Enum(RiskLevel, name="risk_level_enum"), default=RiskLevel.green)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
