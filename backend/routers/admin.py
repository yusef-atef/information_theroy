from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from ..database import get_db
from ..models import User
from ..schemas import UserResponse
import json

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# WebSocket Manager for Real-time Updates
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_update(self, db: AsyncSession):
        """Fetch all users and broadcast to all connected admins."""
        users = await self.get_all_users(db)
        # Convert users to JSON-serializable list
        user_list = [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "file_count": len(u.files)
            }
            for u in users
        ]
        message = json.dumps({"type": "USER_UPDATE", "data": user_list})
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

    async def get_all_users(self, db: AsyncSession):
        result = await db.execute(select(User).options(selectinload(User.files)))
        return result.scalars().all()

manager = ConnectionManager()

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    """Standard REST endpoint for initial load."""
    result = await db.execute(select(User).options(selectinload(User.files)))
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "file_count": len(u.files),
            "created_at": u.created_at
        }
        for u in users
    ]

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await manager.connect(websocket)
    # Send initial data immediately
    await manager.broadcast_update(db)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
