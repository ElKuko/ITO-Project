"""Application configuration from environment variables."""

import os
from pathlib import Path

# Base directory (backend folder)
BASE_DIR = Path(__file__).resolve().parent

# Project root (parent of backend)
PROJECT_ROOT = BASE_DIR.parent

# Database
# For SQLite (development): sqlite:///./ito.db
# For PostgreSQL (production): postgresql://user:pass@host:5432/dbname
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'ito.db'}"
)

# Handle Railway's postgres:// vs postgresql:// issue
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
TOKEN_EXPIRY_SECONDS = int(os.getenv("TOKEN_EXPIRY_SECONDS", "86400"))  # 24 hours

# File uploads (in project root, not backend folder)
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(PROJECT_ROOT / "uploads"))

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)
