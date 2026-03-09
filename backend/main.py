"""Ito Merchandising App — FastAPI entry point."""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import engine, Base
from .routers import auth, stores, skus, approvals, visits, dashboard, users, routes, notifications, chat

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Ito Merchandising API",
    description="Shelf audit and store visit management for Ito merchandisers in Puerto Rico",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ───────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(skus.router)
app.include_router(approvals.router)
app.include_router(visits.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(routes.router)
app.include_router(notifications.router)
app.include_router(chat.router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "ito-merchandising", "version": "0.1.0"}

@app.get("/api/my-ip")
def get_client_ip(request: Request):
    """Returns the client's IP address (useful for finding your phone's local IP)."""
    client_ip = request.client.host if request.client else "unknown"
    return {"ip": client_ip}


# ── Static file serving (must be AFTER all API routes) ───────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

uploads_dir = os.path.join(BASE_DIR, "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

frontend_dir = os.path.join(BASE_DIR, "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
