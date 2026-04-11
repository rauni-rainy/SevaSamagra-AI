"""
SevaSamagra AI - Seed Data Script
=================================

What this script creates and why:
This script populates the database with realistic seed data for the MVP/Demo.
It generates:
- 3 geometric Zones representing neighborhoods in Delhi using PostGIS.
- 10 Volunteers with varying skills and geo-locations.
- 20 Field Reports spanning different urgencies and sources, including voice.
- 2 trigger-based BioAlerts correlated with the aforementioned reports.
- Comprehensive Audit Log traces for these events.

The purpose is to ensure the frontend dashboards, risk maps, and volunteer 
dispatching mechanisms have rich, interconnected data to demonstrate early 
detection capabilities effectively without an empty state.

How to re-run it on a fresh database:
1. Ensure the PostgreSQL database is running and Alembic migrations applied:
   `alembic upgrade head`
2. Run this script via the provided shell helper:
   `bash scripts/run_seed.sh` or `cd backend && python ../scripts/seed_data.py`

How to modify it to add more data:
- Add new coordinates/polygons in the `ZONES_DATA` list below.
- Add strings to `REPORTS_DATA` with appropriate flags or urgency values.
- Link them using standard SQLAlchemy `session.add()` flow as demonstrated.
"""

import sys
import os
import uuid
from datetime import datetime, timedelta
import random

# Append the backend directory so that 'database' and 'models' modules can be found
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from database.connection import SessionLocal
from models.zone import Zone, RiskLevel
from models.report import FieldReport, SourceType, UrgencyLevel
from models.volunteer import Volunteer
from models.alert import BioAlert, AlertSeverity
from models.assignment import VolunteerAssignment, AssignmentStatus
from models.audit_log import AuditLog

# =======================
# Configurations Data
# =======================
ZONES_DATA = [
    {
        "name": "Okhla Industrial Area, South Delhi",
        "city": "Delhi",
        "poly": "POLYGON((77.2650 28.5300, 77.2750 28.5300, 77.2750 28.5400, 77.2650 28.5400, 77.2650 28.5300))",
        "center": (77.2700, 28.5355),
        "bio_risk_index": 0.2,
        "risk_level": RiskLevel.green
    },
    {
        "name": "Kalyanpuri, East Delhi",
        "city": "Delhi",
        "poly": "POLYGON((77.3050 28.6150, 77.3150 28.6150, 77.3150 28.6250, 77.3050 28.6250, 77.3050 28.6150))",
        "center": (77.3100, 28.6200),
        "bio_risk_index": 0.6,    # Overwritten below for demonstration
        "risk_level": RiskLevel.amber # Overwritten below for demonstration 
    },
    {
        "name": "Seemapuri, Shahdara",
        "city": "Delhi",
        "poly": "POLYGON((77.2950 28.6750, 77.3050 28.6750, 77.3050 28.6850, 77.2950 28.6850, 77.2950 28.6750))",
        "center": (77.3000, 28.6800),
        "bio_risk_index": 0.4,
        "risk_level": RiskLevel.green # Overwritten below for demonstration
    }
]

VOLUNTEERS_DATA = [
    ("Amit Sharma", "9876543210", ['medical', 'first_aid']),
    ("Priya Patidar", "9876543211", ['medical', 'first_aid']),
    ("Rahul Singh", "9876543212", ['sanitation', 'water_treatment']),
    ("Neha Gupta", "9876543213", ['sanitation', 'water_treatment']),
    ("Ravi Verma", "9876543214", ['food_distribution', 'logistics']),
    ("Anjali Desai", "9876543215", ['food_distribution', 'logistics']),
    ("Karan Kapoor", "9876543216", ['education', 'counselling']),
    ("Sneha Reddy", "9876543217", ['education', 'counselling']),
    ("Dr. Vikram Rathore", "9876543218", ['medical', 'sanitation']),
    ("Dr. Sunita Menon", "9876543219", ['medical', 'sanitation']),
]

REPORTS_DATA = [
    # Bio-risk (8 cases)
    {"text": "Kal se naali mein paani ruka hua hai, bahut badbu aa rahi hai", "type": "bio", "source": SourceType.whatsapp, "urgency": UrgencyLevel.medium, "biomarkers": ["stagnant water", "foul smell"]},
    {"text": "Stagnant water collecting near the handpump for 3 days", "type": "bio", "source": SourceType.paper, "urgency": UrgencyLevel.medium, "biomarkers": ["stagnant water", "handpump"]},
    {"text": "Three children in building C had stomach pain and loose motions", "type": "bio", "source": SourceType.manual, "urgency": UrgencyLevel.high, "biomarkers": ["stomach pain", "loose motions"]},
    {"text": "Dead rats found near the water tank yesterday", "type": "bio", "source": SourceType.voice, "urgency": UrgencyLevel.high, "biomarkers": ["dead rats", "water tank"]},
    {"text": "Foul smell from open drain, mosquitoes increasing rapidly", "type": "bio", "source": SourceType.whatsapp, "urgency": UrgencyLevel.medium, "biomarkers": ["foul smell", "mosquitoes"]},
    {"text": "Ganda paani aa raha hai nal mein, pet dard ho raha hai", "type": "bio", "source": SourceType.voice, "urgency": UrgencyLevel.high, "biomarkers": ["dirty water", "stomach pain"]},
    {"text": "Sewage overflow on main road since last night", "type": "bio", "source": SourceType.whatsapp, "urgency": UrgencyLevel.critical, "biomarkers": ["sewage overflow"]},
    {"text": "Four families reporting fever and diarrhoea this week", "type": "bio", "source": SourceType.paper, "urgency": UrgencyLevel.high, "biomarkers": ["fever", "diarrhoea"]},

    # Normal requests (6 cases)
    {"text": "Monthly ration supply not received for 12 families", "type": "normal", "source": SourceType.manual, "urgency": UrgencyLevel.low, "biomarkers": []},
    {"text": "School textbooks needed for 20 children in block B", "type": "normal", "source": SourceType.whatsapp, "urgency": UrgencyLevel.low, "biomarkers": []},
    {"text": "Elderly woman needs home medical visit, cannot walk", "type": "normal", "source": SourceType.paper, "urgency": UrgencyLevel.medium, "biomarkers": []},
    {"text": "Winter blankets required for 8 households", "type": "normal", "source": SourceType.whatsapp, "urgency": UrgencyLevel.low, "biomarkers": []},
    {"text": "Vocational training needed for unemployed youth", "type": "normal", "source": SourceType.manual, "urgency": UrgencyLevel.low, "biomarkers": []},
    {"text": "Child vaccination camp requested for the area", "type": "normal", "source": SourceType.whatsapp, "urgency": UrgencyLevel.low, "biomarkers": []},

    # Critical structure (4 cases)
    {"text": "Water pump broken for 4 days, no drinking water available", "type": "critical", "source": SourceType.whatsapp, "urgency": UrgencyLevel.critical, "biomarkers": []},
    {"text": "No electricity in 3 buildings, elderly residents at risk", "type": "critical", "source": SourceType.manual, "urgency": UrgencyLevel.high, "biomarkers": []},
    {"text": "Broken sewer pipe flooding basement of building A", "type": "critical", "source": SourceType.whatsapp, "urgency": UrgencyLevel.critical, "biomarkers": []},
    {"text": "Road collapse blocking ambulance access to the colony", "type": "critical", "source": SourceType.paper, "urgency": UrgencyLevel.critical, "biomarkers": []},
]

def generate_random_point(center_lon, center_lat, offset=0.003):
    """Generate a geographic point slightly varied from a central point."""
    lon = center_lon + random.uniform(-offset, offset)
    lat = center_lat + random.uniform(-offset, offset)
    return f"POINT({lon} {lat})"

def seed_database():
    session = SessionLocal()
    try:
        print("Starting seed process...")

        # ----------------------------------
        # 1. ZONE GENERATOR
        # ----------------------------------
        created_zones = []
        for i, z in enumerate(ZONES_DATA):
            br_index = z['bio_risk_index']
            rl = z['risk_level']
            # Based on the user constraints, we overwrite specifics for Demo logic
            if "Kalyanpuri" in z['name']:
                br_index = 0.8
                rl = RiskLevel.red
            elif "Seemapuri" in z['name']:
                br_index = 0.6
                rl = RiskLevel.amber

            zone = Zone(
                name=z['name'],
                city=z['city'],
                boundary=f"SRID=4326;{z['poly']}", 
                bio_risk_index=br_index,
                risk_level=rl
            )
            session.add(zone)
            session.commit()
            session.refresh(zone)
            created_zones.append(zone)

        # ----------------------------------
        # 2. VOLUNTEERS
        # ----------------------------------
        created_vols = []
        for idx, (name, phone, skills) in enumerate(VOLUNTEERS_DATA):
            assigned_zone = created_zones[idx % 3]
            point = generate_random_point(ZONES_DATA[idx % 3]["center"][0], ZONES_DATA[idx % 3]["center"][1])
            vol = Volunteer(
                name=name,
                phone=phone,
                skills=skills,
                current_location=f"SRID=4326;{point}",
                is_available=True,
                zone_id=assigned_zone.id
            )
            session.add(vol)
            session.commit()
            created_vols.append(vol)

        # ----------------------------------
        # 3. FIELD REPORTS
        # ----------------------------------
        created_reports = []
        for rep in REPORTS_DATA:
            # Map intelligence securely to target zones explicitly requested 
            if rep['type'] == 'bio':
                 if "stomach pain" in rep['text'] or "stagnant water" in rep['text'].lower():
                     assigned_zone = next(z for z in created_zones if "Kalyanpuri" in z.name)
                 else:
                     assigned_zone = next(z for z in created_zones if "Seemapuri" in z.name)
            else:
                 assigned_zone = random.choice(created_zones)

            # Match center for geolocation variance
            zn_data = next(zd for zd in ZONES_DATA if assigned_zone.name == zd['name'])
            point = generate_random_point(zn_data['center'][0], zn_data['center'][1])
            
            # Scatter timestamps arbitrarily across prior 7 days
            reported_time = datetime.utcnow() - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23))

            report = FieldReport(
                zone_id=assigned_zone.id,
                source_type=rep['source'],
                raw_text=rep['text'],
                extracted_need="Immediate attention needed" if rep['urgency'] in [UrgencyLevel.high, UrgencyLevel.critical] else "Normal request",
                extracted_location=assigned_zone.name.split(',')[0],
                urgency_level=rep['urgency'],
                bio_markers_detected=rep['biomarkers'],
                coordinates=f"SRID=4326;{point}",
                reported_at=reported_time
            )
            session.add(report)
            session.commit()
            session.refresh(report)
            created_reports.append(report)

        # ----------------------------------
        # 4. BIO-ALERTS 
        # ----------------------------------
        # 4a. Kalyanpuri Alert (focused on stomach-pain / stagnant water)
        kal_zone = next(z for z in created_zones if "Kalyanpuri" in z.name)
        kal_reports = [r.id for r in created_reports if r.zone_id == kal_zone.id and ("stomach pain" in r.raw_text or "stagnant" in r.raw_text.lower())]
        
        kal_alert = BioAlert(
            zone_id=kal_zone.id,
            alert_type="waterborne_disease_risk",
            triggered_by_reports=[str(i) for i in kal_reports],
            severity=AlertSeverity.warning,
            is_active=True,
            recommended_skills=['medical', 'sanitation']
        )
        session.add(kal_alert)

        # 4b. Seemapuri Alert (focused on fever outbreak likelihood)
        see_zone = next(z for z in created_zones if "Seemapuri" in z.name)
        see_reports = [r.id for r in created_reports if r.zone_id == see_zone.id and "fever" in r.raw_text.lower()]
        
        see_alert = BioAlert(
            zone_id=see_zone.id,
            alert_type="fever_outbreak_risk",
            triggered_by_reports=[str(i) for i in see_reports],
            severity=AlertSeverity.watch,
            is_active=True,
            recommended_skills=['medical', 'sanitation']
        )
        session.add(see_alert)
        session.commit()
        session.refresh(kal_alert)
        session.refresh(see_alert)

        # ----------------------------------
        # 5. AUDIT LOGS (Immutable record generation)
        # ----------------------------------
        audit1 = AuditLog(
            action='alert_fired',
            entity_type='BioAlert',
            entity_id=kal_alert.id,
            payload={"severity": kal_alert.severity.value, "zone": kal_zone.name},
            performed_by="System"
        )
        audit2 = AuditLog(
            action='alert_fired',
            entity_type='BioAlert',
            entity_id=see_alert.id,
            payload={"severity": see_alert.severity.value, "zone": see_zone.name},
            performed_by="System"
        )
        session.add_all([audit1, audit2])
        session.commit()

        # Final Verification -------------------------------
        print(f"Seeded: {len(created_zones)} zones, {len(created_vols)} volunteers, {len(created_reports)} reports, 2 alerts")

    except Exception as e:
        print(f"Error seeding data: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    seed_database()
