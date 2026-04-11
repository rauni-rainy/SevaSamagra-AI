# SevaSamagra AI

**Smart Evidence-driven Volunteer Allocation system for NGOs.**
It digitizes paper surveys, voice reports, and field data, then uses AI to detect community health risks early and dispatch the right volunteers intelligently.

## Tech Stack
- **Frontend:** Next.js 14, TypeScript, Tailwind CSS, Leaflet.js, Socket.io-client, Zustand
- **Backend:** Python FastAPI, spaCy, python-socketio
- **Database:** PostgreSQL with PostGIS, SQLAlchemy, Alembic
- **Voice / AI:** Twilio (IVR), OpenAI Whisper API
- **Deployment:** Vercel (Frontend), Railway (Backend + DB)

## Local Development Setup

### Prerequisites
- Node.js (v18+)
- Python 3.10+
- PostgreSQL + PostGIS

### 1. Setting Up the Backend
```bash
cd backend
python -m venv venv
# On Windows: venv\Scripts\activate
# On Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Update the .env file with your specific variables
python main.py
```

### 2. Setting Up the Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Environment Variables

All necessary variables are listed in `.env.example`. A breakdown:
- `ENVIRONMENT`: deployment tier (development, staging, production)
- `SECRET_KEY`: Used by FastAPI for backend security
- `DATABASE_URL`: PostgreSQL connection string (ensure PostGIS is enabled)
- `OPENAI_API_KEY`: API key for Whisper and language parsing tasks
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`: Used for voice IVR alerts
- `FRONTEND_URL`: Helps with CORS policy on the backend

## Deployment Guide

### Vercel (Frontend)
1. Import the frontend directory to Vercel.
2. Set build command: `npm run build`, output directory: `.next`.
3. Set environment variables mimicking your `.env.local` specifics.
4. Deploy!

### Railway (Backend & Database)
1. Provision a PostgreSQL container on Railway, and add the PostGIS extension.
2. Link the GitHub repository and target the `backend/` directory for Python deployment.
3. Add the DB connection string as `DATABASE_URL` in Railway variables.
4. Add all other related keys (OpenAI, Twilio). 
5. Railway will detect `requirements.txt` and install dependencies. Start command should ideally be: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
