# SevaSamagra AI

**A Comprehensive Intelligent Operating System for the NGO and Social Impact Ecosystem.**

SevaSamagra AI transforms unstructured field data—like voice calls and on-the-ground observations—into actionable spatial intelligence. By bridging the gap between field reporting and central coordination, it enables rapid, data-driven disaster relief, volunteer dispatch, and hazard management.


<img width="1900" height="866" alt="Screenshot 2026-04-14 125758" src="https://github.com/user-attachments/assets/69ab3b11-c7ca-4262-b495-2b8631d782c0" />

## 🚀 Key Features

- **Zero-UI Voice Pipeline:** Ingests field reports via phone calls using Twilio, transcribes them, and extracts structured data (location, severity, hazard type) using **Google Gemini AI**.
- **Real-Time Spatial Intelligence:** A live, high-fidelity interactive dashboard built with **Google Maps API** that visualizes bio-risk zones, active alerts, and volunteer positions.
- **Intelligent Volunteer Dispatch:** An advanced matching engine powered by **PostGIS** that assigns volunteers based on geographic proximity and specific skill sets required for the crisis.
- **Commendation & Reputation System:** Allows field coordinators to award honor points and feedback to volunteers, maintaining motivation and tracking performance over time.
- **Live Synchronization:** Utilizes WebSockets to ensure all coordinators see updates, new alerts, and dispatched assignments in real time without refreshing.

## 🛠️ Technology Stack

### Frontend (Next.js App Router)
- **Framework:** Next.js 16, React 19, TypeScript
- **Styling:** Tailwind CSS
- **Mapping:** `@vis.gl/react-google-maps` (Google Maps API)
- **State Management:** Zustand
- **Real-time:** `socket.io-client`

### Backend (FastAPI)
- **Framework:** Python FastAPI
- **Database ORM:** SQLAlchemy with GeoAlchemy2
- **AI Integration:** Google Generative AI (`google-genai`), spaCy
- **Telephony:** Twilio
- **Real-time:** `python-socketio`

### Infrastructure
- **Database:** PostgreSQL with **PostGIS** extension
- **Deployment:** Google Cloud Run 

---

## 💻 Local Development Setup

### Prerequisites
- Node.js (v18+)
- Python 3.10+
- PostgreSQL database with PostGIS extension enabled
- Google Maps API Key
- Google Gemini API Key
- Twilio Account (for voice features)

### 1. Database Setup
Ensure you have a PostgreSQL database running and install the PostGIS extension:
```sql
CREATE EXTENSION postgis;
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Environment variables setup
cp .env.example .env
# Edit .env with your DATABASE_URL, GEMINI_API_KEY, TWILIO credentials, etc.

# Run database migrations
alembic upgrade head

# Start the FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Environment variables setup
cp .env.example .env.local
# Edit .env.local and add:
# NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=your_google_maps_key
# NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
# NEXT_PUBLIC_WS_URL=http://localhost:8000

# Start the Next.js development server
npm run dev
```

---

## 🌍 Environment Variables

### Backend (`backend/.env`)
- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:pass@localhost/seva`)
- `GEMINI_API_KEY`: API key for Google Gemini for parsing reports.
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`: For the voice IVR pipeline.
- `FRONTEND_URL`: For CORS configuration (e.g., `http://localhost:3000`).

### Frontend (`frontend/.env.local`)
- `NEXT_PUBLIC_BACKEND_URL`: The REST API URL of your backend.
- `NEXT_PUBLIC_WS_URL`: The WebSocket URL of your backend.
- `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`: Required for the interactive map dashboard.

---

## ☁️ Deployment

### Backend and Frontend (Google Cloud Run)
The backend is containerized and designed to be deployed on Google Cloud Run. Ensure you have the `gcloud` CLI installed and authenticated. Set your environment variables in the Cloud Run service configuration and ensure your Cloud Run service has access to your managed PostgreSQL database (e.g., via Cloud SQL connector).



---

## 🤝 Contributing
Contributions are welcome! Please open an issue or submit a pull request if you'd like to help expand the SevaSamagra AI ecosystem.

## 📄 License
This project is licensed under the MIT License.
