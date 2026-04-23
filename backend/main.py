"""
main.py — FastAPI Application Entry Point for SecureCorrect
"""

import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is in sys.path for absolute imports
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.database import create_tables
from backend.routers import auth, files, admin


# ---------------------------------------------------------------------------
# Lifespan — runs on startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create DB tables if they don't exist
    await create_tables()
    yield
    # Shutdown: nothing to clean up for SQLite dev setup


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SecureCorrect API",
    description=(
        "Fault-Tolerant Cloud Storage with Reed-Solomon Error-Correcting Authentication. "
        "Supports resilient login via Galois Field ECC — minor password typos are "
        "mathematically corrected before key derivation."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow the Flutter app (and local dev) to reach the API
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(files.router)
app.include_router(admin.router)

# Mount static files for the Admin Panel
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/admin")
async def get_admin_panel():
    return FileResponse(str(STATIC_DIR / "admin.html"))


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "message": "Welcome to SecureCorrect API",
        "status": "online",
        "version": "1.0.0",
        "ecc_capacity": "2 errors / 4 erasures"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
