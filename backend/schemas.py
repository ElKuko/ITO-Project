"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Auth ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    full_name: str


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    region: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "merchandiser"
    region: Optional[str] = None


# ── Stores ────────────────────────────────────────────────────────────────

class StoreCreate(BaseModel):
    name: str
    region: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class StoreOut(BaseModel):
    id: int
    name: str
    region: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool

    class Config:
        from_attributes = True


# ── SKUs ──────────────────────────────────────────────────────────────────

class SKUCreate(BaseModel):
    name: str
    brand: str
    category: Optional[str] = None
    barcode: Optional[str] = None
    image_url: Optional[str] = None


class SKUOut(BaseModel):
    id: int
    name: str
    brand: str
    category: Optional[str] = None
    barcode: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# ── Store-SKU Approvals ──────────────────────────────────────────────────

class ApprovalCreate(BaseModel):
    store_id: int
    sku_id: int
    quarter: str


class ApprovalOut(BaseModel):
    id: int
    store_id: int
    sku_id: int
    quarter: str
    approved_at: datetime
    sku: Optional[SKUOut] = None
    store: Optional[StoreOut] = None

    class Config:
        from_attributes = True


# ── Visit SKU Actions ────────────────────────────────────────────────────

class VisitSKUActionCreate(BaseModel):
    sku_id: int
    action_type: str  # needs_refill | placed_on_shelf | needs_order
    notes: Optional[str] = None


class VisitSKUActionOut(BaseModel):
    id: int
    sku_id: int
    action_type: str
    notes: Optional[str] = None
    sku: Optional[SKUOut] = None

    class Config:
        from_attributes = True


# ── Store Visits ─────────────────────────────────────────────────────────

class StoreVisitCreate(BaseModel):
    store_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None
    sku_actions: list[VisitSKUActionCreate] = []


class VisitPhotoOut(BaseModel):
    id: int
    file_path: str
    uploaded_at: datetime
    cv_processed: bool
    cv_results: Optional[str] = None

    class Config:
        from_attributes = True


class StoreVisitOut(BaseModel):
    id: int
    store_id: int
    user_id: int
    visited_at: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None
    status: str
    sku_actions: list[VisitSKUActionOut] = []
    photos: list[VisitPhotoOut] = []
    store: Optional[StoreOut] = None
    user: Optional[UserOut] = None

    class Config:
        from_attributes = True


# ── CV Results ───────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class VoidRegion(BaseModel):
    bbox: BoundingBox
    confidence: float


class DetectedProduct(BaseModel):
    label: str
    bbox: BoundingBox
    confidence: float
    facings_count: int = 1


class CVResult(BaseModel):
    void_space_score: float  # 0-1
    void_regions: list[VoidRegion] = []
    detected_products: list[DetectedProduct] = []
    image_width: int
    image_height: int


# ── Dashboard ────────────────────────────────────────────────────────────

class DashboardFilters(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    region: Optional[str] = None
    store_id: Optional[int] = None
    sku_id: Optional[int] = None
    merchandiser_id: Optional[int] = None
