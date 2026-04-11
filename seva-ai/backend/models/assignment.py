from sqlalchemy import Column, DateTime, ForeignKey, Enum, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from database.connection import Base
from sqlalchemy.sql import func
import uuid
import enum

class AssignmentStatus(str, enum.Enum):
    assigned = 'assigned'
    en_route = 'en_route'
    on_site = 'on_site'
    completed = 'completed'

class VolunteerAssignment(Base):
    __tablename__ = "volunteer_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey('bio_alerts.id'), index=True, nullable=False)
    volunteer_id = Column(UUID(as_uuid=True), ForeignKey('volunteers.id'), index=True, nullable=False)
    assigned_at = Column(DateTime, default=func.now())
    status = Column(Enum(AssignmentStatus, name="assignment_status_enum"), default=AssignmentStatus.assigned)
    notes = Column(Text, nullable=True)
    points_awarded = Column(Integer, default=0)
    feedback_comment = Column(Text, nullable=True)

