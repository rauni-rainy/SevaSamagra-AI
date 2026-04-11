from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database.init_db import initialize_database
from routers import reports, zones, volunteers, alerts, voice, assignments, audit
from websocket.socket_manager import socket_manager
import socketio
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SEVA AI API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    try:
        initialize_database()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    origin = request.headers.get("origin", settings.FRONTEND_URL)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        },
    )

app.include_router(reports.router, prefix="/api/v1")
app.include_router(zones.router, prefix="/api/v1")
app.include_router(volunteers.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")
app.include_router(assignments.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """
    Check API health and runtime environment.
    """
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }

# Wrap FastAPI app with socketio ASGI application
asgi_app = socketio.ASGIApp(socket_manager.sio, other_asgi_app=app, socketio_path="/ws/socket.io")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:asgi_app", host="0.0.0.0", port=8000, reload=True)
