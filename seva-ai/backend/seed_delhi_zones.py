"""
seed_delhi_zones.py — Seeds realistic Delhi bio-risk zones and field reports
Run from backend directory: python seed_delhi_zones.py
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from sqlalchemy.orm import Session
from database.connection import SessionLocal
from models.zone import Zone, RiskLevel
from models.report import FieldReport, SourceType, UrgencyLevel
from models.alert import BioAlert, AlertSeverity
import uuid

# ─── Delhi Zone Polygons (real neighbourhood boundaries, approx) ─────────────
# Each polygon is a list of [lon, lat] pairs forming a closed ring

DELHI_ZONES = [
    {
        "name": "Seemapuri G-Block Colony",
        "city": "Delhi",
        "risk_level": RiskLevel.red,
        "bio_risk_index": 6.5,
        # Seemapuri area near Bus Depot
        "polygon": [
            [77.3178, 28.6880], [77.3248, 28.6880],
            [77.3248, 28.6820], [77.3178, 28.6820],
            [77.3178, 28.6880],
        ],
        "reports": [
            {
                "raw_text": "Haan ji, main Delhi ke Seemapuri area se bol raha hoon — Seemapuri Bus Depot ke paas jo G-Block colony hai, wahan Lane 4 se. Naali 4 din se puri tarah band hai, gutter ka paani sadak pe aa gaya hai. Municipal water supply pipe toota hua hai, 6 ghar ke log ulti aur dast se peedit hain, 3 bachche shamil hain. Ek buda — 68 saal ke — Dr. Hedgewar hospital mein admit karna pada.",
                "extracted_need": "Severe sewage overflow and contaminated water supply in Seemapuri G-Block; 6 households affected with vomiting and diarrhea including 3 children; 1 elderly hospitalised.",
                "extracted_location": "Seemapuri G-Block Colony, Lane 4",
                "urgency_level": UrgencyLevel.critical,
                "source_type": SourceType.voice,
                "bio_markers_detected": ["sanitation_failure", "waterborne_risk", "stagnant_water", "vector_risk", "fever_cluster"],
                "latitude": 28.6854,
                "longitude": 77.3210,
            },
            {
                "raw_text": "Seemapuri Bus Depot ke saamne ka nala overflow ho gaya hai, raat bhar paani jama raha. Macchar bahut ho gaye hain.",
                "extracted_need": "Drain overflow in front of Seemapuri Bus Depot causing stagnant water and mosquito breeding.",
                "extracted_location": "Seemapuri Bus Depot",
                "urgency_level": UrgencyLevel.high,
                "source_type": SourceType.whatsapp,
                "bio_markers_detected": ["stagnant_water", "vector_risk", "sanitation_failure"],
                "latitude": 28.6841,
                "longitude": 77.3225,
            },
        ]
    },
    {
        "name": "Dharavi-Style — Karol Bagh Locality",
        "city": "Delhi",
        "risk_level": RiskLevel.amber,
        "bio_risk_index": 3.2,
        # Karol Bagh core area
        "polygon": [
            [77.1850, 28.6520], [77.1960, 28.6520],
            [77.1960, 28.6440], [77.1850, 28.6440],
            [77.1850, 28.6520],
        ],
        "reports": [
            {
                "raw_text": "Karol Bagh Locality mein sewage line kal raat se band hai. Ghar ke bahar paani aa raha hai. Water quality bahut kharab lag rahi hai.",
                "extracted_need": "Blocked sewage line in Karol Bagh causing overflow; water quality reported as poor.",
                "extracted_location": "Karol Bagh Locality",
                "urgency_level": UrgencyLevel.medium,
                "source_type": SourceType.voice,
                "bio_markers_detected": ["waterborne_risk", "sanitation_failure"],
                "latitude": 28.6490,
                "longitude": 77.1902,
            },
        ]
    },
    {
        "name": "Yamuna Pushta Cluster",
        "city": "Delhi",
        "risk_level": RiskLevel.red,
        "bio_risk_index": 7.8,
        # Along Yamuna near Sonia Vihar
        "polygon": [
            [77.2680, 28.7200], [77.2820, 28.7200],
            [77.2820, 28.7110], [77.2680, 28.7110],
            [77.2680, 28.7200],
        ],
        "reports": [
            {
                "raw_text": "Yamuna Pushta ke paas bahut zyada paani jama hua hai, flood jaisi situation hai. 50 se zyada log affected hain. Bachche bukhar mein hain.",
                "extracted_need": "Massive waterlogging near Yamuna Pushta affecting 50+ people; children running high fever.",
                "extracted_location": "Yamuna Pushta, near Sonia Vihar",
                "urgency_level": UrgencyLevel.critical,
                "source_type": SourceType.voice,
                "bio_markers_detected": ["stagnant_water", "waterborne_risk", "vector_risk", "fever_cluster", "sanitation_failure"],
                "latitude": 28.7155,
                "longitude": 77.2748,
            },
            {
                "raw_text": "Yamuna ke paas dead animals hain, bahut badbu aa rahi hai. Paani mein contamination ka darr hai.",
                "extracted_need": "Dead animal carcasses near Yamuna riverbank causing contamination risk and foul odour.",
                "extracted_location": "Yamuna Pushta",
                "urgency_level": UrgencyLevel.high,
                "source_type": SourceType.whatsapp,
                "bio_markers_detected": ["animal_hazard", "waterborne_risk", "waste_accumulation"],
                "latitude": 28.7170,
                "longitude": 77.2735,
            },
        ]
    },
    {
        "name": "Okhla Industrial Sector",
        "city": "Delhi",
        "risk_level": RiskLevel.amber,
        "bio_risk_index": 2.8,
        # Okhla Phase II area
        "polygon": [
            [77.3040, 28.5320], [77.3180, 28.5320],
            [77.3180, 28.5220], [77.3040, 28.5220],
            [77.3040, 28.5320],
        ],
        "reports": [
            {
                "raw_text": "Okhla Phase 2 mein factory ke paas chemical smell aa rahi hai, kai logon ko aankhon mein jalan ho rahi hai aur saans lene mein dikkat.",
                "extracted_need": "Chemical odour from factory in Okhla Phase 2 causing respiratory irritation and eye burning in nearby residents.",
                "extracted_location": "Okhla Phase 2, Industrial Area",
                "urgency_level": UrgencyLevel.high,
                "source_type": SourceType.manual,
                "bio_markers_detected": ["respiratory_hazard"],
                "latitude": 28.5278,
                "longitude": 77.3105,
            },
        ]
    },
    {
        "name": "Seelampur Urban Village",
        "city": "Delhi",
        "risk_level": RiskLevel.green,
        "bio_risk_index": 1.0,
        # Seelampur area, East Delhi
        "polygon": [
            [77.2740, 28.6680], [77.2850, 28.6680],
            [77.2850, 28.6600], [77.2740, 28.6600],
            [77.2740, 28.6680],
        ],
        "reports": [
            {
                "raw_text": "Seelampur mein ek jagah paani thoda bhar gaya hai pump ke paas, but situation abhi control mein hai.",
                "extracted_need": "Minor waterlogging near water pump in Seelampur; situation under control but monitoring required.",
                "extracted_location": "Seelampur, near water pump",
                "urgency_level": UrgencyLevel.low,
                "source_type": SourceType.voice,
                "bio_markers_detected": ["stagnant_water"],
                "latitude": 28.6638,
                "longitude": 77.2792,
            },
        ]
    },
    {
        "name": "Rohini Sector 15 Colony",
        "city": "Delhi",
        "risk_level": RiskLevel.green,
        "bio_risk_index": 0.5,
        # Rohini Sec 15
        "polygon": [
            [77.0820, 28.7300], [77.0950, 28.7300],
            [77.0950, 28.7210], [77.0820, 28.7210],
            [77.0820, 28.7300],
        ],
        "reports": []
    },
]

def make_wkt_polygon(coords: list) -> str:
    """Convert list of [lon, lat] pairs to WKT POLYGON string."""
    pts = ", ".join(f"{c[0]} {c[1]}" for c in coords)
    return f"SRID=4326;POLYGON(({pts}))"


def seed():
    db: Session = SessionLocal()
    
    try:
        seeded_zones = 0
        seeded_reports = 0
        seeded_alerts = 0

        for zdata in DELHI_ZONES:
            # Check if zone already exists by name
            existing = db.query(Zone).filter(Zone.name == zdata["name"]).first()
            if existing:
                print(f"  [SKIP] Zone already exists: {zdata['name']}")
                zone = existing
            else:
                wkt = make_wkt_polygon(zdata["polygon"])
                zone = Zone(
                    name=zdata["name"],
                    city=zdata["city"],
                    risk_level=zdata["risk_level"],
                    bio_risk_index=zdata["bio_risk_index"],
                    boundary=wkt,
                )
                db.add(zone)
                db.flush()  # Get zone.id before committing
                seeded_zones += 1
                print(f"  [OK] Zone: {zone.name} [{zone.risk_level}] bio_risk={zone.bio_risk_index}")

                # Create a BioAlert for red/amber zones
                if zdata["risk_level"] in (RiskLevel.red, RiskLevel.amber):
                    severity = AlertSeverity.critical if zdata["risk_level"] == RiskLevel.red else AlertSeverity.warning
                    alert = BioAlert(
                        zone_id=zone.id,
                        alert_type="Seeded Risk Zone",
                        triggered_by_reports=["sanitation_failure", "waterborne_risk"],
                        severity=severity,
                        recommended_skills=["medical", "sanitation", "first_aid"],
                    )
                    db.add(alert)
                    seeded_alerts += 1

            # Seed reports for this zone
            for rdata in zdata.get("reports", []):
                lat = rdata["latitude"]
                lon = rdata["longitude"]
                coords_str = f"SRID=4326;POINT({lon} {lat})"

                report = FieldReport(
                    zone_id=zone.id,
                    source_type=rdata["source_type"],
                    raw_text=rdata["raw_text"],
                    extracted_need=rdata["extracted_need"],
                    extracted_location=rdata["extracted_location"],
                    urgency_level=rdata["urgency_level"],
                    bio_markers_detected=rdata["bio_markers_detected"],
                    latitude=lat,
                    longitude=lon,
                    coordinates=coords_str,
                )
                db.add(report)
                seeded_reports += 1

        db.commit()
        print("\nSeeding complete!")
        print(f"   Zones  : {seeded_zones} created")
        print(f"   Reports: {seeded_reports} created")
        print(f"   Alerts : {seeded_alerts} created")

    except Exception as e:
        db.rollback()
        print(f"\nSeeding FAILED: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding Delhi bio-risk zones and field reports...\n")
    seed()
