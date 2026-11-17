"""Ito Merchandising App — FastAPI entry point."""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect, text

from .database import engine, Base, SessionLocal
from .models import SKU, User, Store
from .routers import auth, stores, skus, approvals, visits, dashboard, users, routes, notifications, chat, annotations, reports, work_items

# Create all tables
Base.metadata.create_all(bind=engine)


def add_missing_columns():
    """create_all() never alters existing tables, so add any column the models define
    that an older database is missing (e.g. a local ito.db created by an earlier version).
    Columns are added as nullable; existing rows get NULL or the column's simple default."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                default = ""
                if isinstance(column.default.arg if column.default is not None else None, (bool, int, float, str)):
                    value = column.default.arg
                    default = f" DEFAULT {int(value) if isinstance(value, bool) else repr(value)}"
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {col_type}{default}'))
                print(f"Added missing column {table.name}.{column.name}")


add_missing_columns()


def seed_if_empty():
    """Auto-seed database if it's empty (no users)."""
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            print("Database empty — seeding users, stores, and SKUs...")
            # First seed users, stores, demo SKUs
            from backend.seed import seed
            seed()
            # Then seed the real Ito product SKUs
            from scripts.seed_all_skus import seed_all
            seed_all()
    except Exception as e:
        print(f"Auto-seed check failed: {e}")
    finally:
        db.close()


# Run auto-seed on startup
seed_if_empty()

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

@app.middleware("http")
async def revalidate_app_files(request: Request, call_next):
    """Make browsers check for a newer app.js/style.css/index.html on every load
    (cheap: unchanged files come back as 304), so phones don't keep running old code."""
    response = await call_next(request)
    path = request.url.path
    if not path.startswith(("/api/", "/uploads/")):
        response.headers["Cache-Control"] = "no-cache"
    return response


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
app.include_router(annotations.router)
app.include_router(reports.router)
app.include_router(work_items.router)

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
