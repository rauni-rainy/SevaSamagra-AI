import socketio
import logging
from config import settings

logger = logging.getLogger(__name__)

class SocketManager:
    def __init__(self):
        self.sio = socketio.AsyncServer(
            cors_allowed_origins='*',
            async_mode='asgi'
        )
        
        @self.sio.event
        async def connect(sid, environ, auth):
            logger.info(f"Client connected: {sid}")

        @self.sio.event
        async def disconnect(sid):
            logger.info(f"Client disconnected: {sid}")

    async def emit_new_report(self, report_data: dict):
        await self.sio.emit('new_report', report_data)

    async def emit_zone_update(self, zone_data: dict):
        await self.sio.emit('zone_update', zone_data)

    async def emit_new_alert(self, alert_data: dict):
        await self.sio.emit('new_alert', alert_data)

    async def emit_volunteer_assigned(self, data: dict):
        await self.sio.emit('volunteer_assigned', data)

socket_manager = SocketManager()
