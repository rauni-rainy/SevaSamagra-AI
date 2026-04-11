"""initial_schema

Revision ID: 0001
Revises: 
Create Date: 2026-04-05 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # We assume 'postgis' extension is created prior or globally, 
    # but we can enforce it here
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis;')

    # Create Enums
    risk_level_enum = postgresql.ENUM('green', 'amber', 'red', name='risk_level_enum')
    risk_level_enum.create(op.get_bind())

    source_type_enum = postgresql.ENUM('voice', 'paper', 'whatsapp', 'manual', name='source_type_enum')
    source_type_enum.create(op.get_bind())

    urgency_level_enum = postgresql.ENUM('low', 'medium', 'high', 'critical', name='urgency_level_enum')
    urgency_level_enum.create(op.get_bind())

    alert_severity_enum = postgresql.ENUM('watch', 'warning', 'critical', name='alert_severity_enum')
    alert_severity_enum.create(op.get_bind())

    assignment_status_enum = postgresql.ENUM('assigned', 'en_route', 'on_site', 'completed', name='assignment_status_enum')
    assignment_status_enum.create(op.get_bind())

    # Create tables
    op.create_table('zones',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('city', sa.String(), nullable=False),
        sa.Column('boundary', geoalchemy2.types.Geometry(geometry_type='POLYGON', from_text='ST_GeomFromEWKT', name='geometry', spatial_index=True), nullable=True),
        sa.Column('bio_risk_index', sa.Float(), nullable=True),
        sa.Column('risk_level', postgresql.ENUM(name='risk_level_enum', create_type=False), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_zones_name'), 'zones', ['name'], unique=False)
    # create index specifically via general alembic or standard sqlalchemy setup
    # Because of spatial_index=True, Geoalchemy's geometry type handles DDL in Postgres.

    op.create_table('field_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('zone_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_type', postgresql.ENUM(name='source_type_enum', create_type=False), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('extracted_need', sa.String(), nullable=True),
        sa.Column('extracted_location', sa.String(), nullable=True),
        sa.Column('urgency_level', postgresql.ENUM(name='urgency_level_enum', create_type=False), nullable=False),
        sa.Column('bio_markers_detected', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('coordinates', geoalchemy2.types.Geometry(geometry_type='POINT', from_text='ST_GeomFromEWKT', name='geometry', spatial_index=True), nullable=True),
        sa.Column('reported_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['zone_id'], ['zones.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_field_reports_reported_at'), 'field_reports', ['reported_at'], unique=False)
    op.create_index(op.f('ix_field_reports_zone_id'), 'field_reports', ['zone_id'], unique=False)

    op.create_table('volunteers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('skills', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('current_location', geoalchemy2.types.Geometry(geometry_type='POINT', from_text='ST_GeomFromEWKT', name='geometry', spatial_index=True), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.Column('zone_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['zone_id'], ['zones.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_volunteers_is_available'), 'volunteers', ['is_available'], unique=False)
    op.create_index(op.f('ix_volunteers_zone_id'), 'volunteers', ['zone_id'], unique=False)

    op.create_table('bio_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('zone_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alert_type', sa.String(), nullable=False),
        sa.Column('triggered_by_reports', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('severity', postgresql.ENUM(name='alert_severity_enum', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('recommended_skills', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['zone_id'], ['zones.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bio_alerts_is_active'), 'bio_alerts', ['is_active'], unique=False)
    op.create_index(op.f('ix_bio_alerts_zone_id'), 'bio_alerts', ['zone_id'], unique=False)

    op.create_table('volunteer_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('volunteer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('status', postgresql.ENUM(name='assignment_status_enum', create_type=False), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['bio_alerts.id'], ),
        sa.ForeignKeyConstraint(['volunteer_id'], ['volunteers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_volunteer_assignments_alert_id'), 'volunteer_assignments', ['alert_id'], unique=False)
    op.create_index(op.f('ix_volunteer_assignments_volunteer_id'), 'volunteer_assignments', ['volunteer_id'], unique=False)

    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('performed_by', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_id'), 'audit_logs', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_type'), 'audit_logs', ['entity_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('volunteer_assignments')
    op.drop_table('bio_alerts')
    op.drop_table('volunteers')
    op.drop_table('field_reports')
    op.drop_table('zones')

    postgresql.ENUM(name='assignment_status_enum').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='alert_severity_enum').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='urgency_level_enum').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='source_type_enum').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='risk_level_enum').drop(op.get_bind(), checkfirst=True)
