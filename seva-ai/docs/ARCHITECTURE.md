# SevaSamagra AI - Architecture Documentation

SevaSamagra AI is designed with a 5-layer architecture to handle ingestion, analysis, mapping, routing, and auditing in real-time.

## Layer 1: Data Ingestion (The Senses)
- **Voice Pipeline:** Twilio IVR combined with OpenAI Whisper API for processing voice reports from the field.
- **Paper OCR:** Automated digitization of physical surveys.
- **WhatsApp Integration:** Conversational interfaces for remote data collection.

## Layer 2: Bio-social Intelligence Scanner (The Brain)
- **NLP Health Risk Detection:** Utilizes `spaCy` to parse and extract critical socio-health markers from unstructured text.
- **LLM Synthesis:** Aggregates multi-source data to predict community health risks and spot emerging trends early.

## Layer 3: Community Digital Twin (The Map)
- **PostGIS Live Map:** Provides geospatial awareness of reported issues and active volunteers.
- **Real-time Synchronization:** Socket.io combined with Next.js and Leaflet.js streams real-time updates onto a dashboard for ops managers.

## Layer 4: Volunteer Routing Engine (The Muscles)
- **Skill + Proximity Matching:** An intelligent dispatcher logic that matches a volunteer's specific skill sets (e.g., medical, logistical) with an incident's location.
- Algorithms utilize PostgreSQL's distance matching (PostGIS) to minimize response times.

## Layer 5: Immutable Audit Log (The Memory)
- Ensures all alerts, dispatches, and resolutions are securely logged.
- Used for analyzing effectiveness, policy making, and performance tracking.

## Database Schema (PostgreSQL + PostGIS)

The core domain relies on spatial-enabled relational tables with GiST indexes for rapid distance matching and geospatial queries.

| Table | Role in System | Key Columns |
|-------|----------------|-------------|
| **zones** | Represents geographic neighborhoods or coverage areas. Used for clustering reports and assigning volunteers by region. | `boundary` (POLYGON), `risk_level`, `bio_risk_index` |
| **field_reports** | Stores raw intelligence from field workers or digital ingestion nodes. | `coordinates` (POINT), `source_type`, `bio_markers_detected`, `extracted_need` |
| **volunteers** | Keeps track of actionable human assets in the field. | `current_location` (POINT), `is_available`, `skills` |
| **bio_alerts** | Aggregates field_reports into actionable anomalies. | `severity`, `triggered_by_reports`, `recommended_skills` |
| **volunteer_assignments** | Connects alerts to specific volunteers to govern dispatch status. | `alert_id`, `volunteer_id`, `status` |
| **audit_logs** | Centralizes immutable state changes for post-action accountability and review. | `action`, `entity_type`, `payload` |
