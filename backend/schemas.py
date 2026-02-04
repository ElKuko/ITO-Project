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
    approved_by: Optional[int] = None
    sku: Optional[SKUOut] = None
    store: Optional[StoreOut] = None

    class Config:
        from_attributes = True


class ApprovalBulkUpdate(BaseModel):
    """Bulk update approved SKUs for a store."""
    store_id: int
    quarter: str
    sku_ids: list[int]  # Complete list of approved SKU IDs


class ApprovalAuditOut(BaseModel):
    id: int
    store_id: int
    user_id: int
    action: str  # added | removed
    sku_id: int
    quarter: str
    timestamp: datetime
    sku: Optional[SKUOut] = None
    user: Optional[UserOut] = None

    class Config:
        from_attributes = True


# ── Visit Photos ─────────────────────────────────────────────────────────

class PhotoUploadMeta(BaseModel):
    """Metadata sent with photo upload."""
    photo_type: str  # arrival_proof | shelf_before | shelf_after
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    captured_at: Optional[datetime] = None


class VisitPhotoOut(BaseModel):
    id: int
    photo_type: str
    file_path: str
    captured_at: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    cv_processed: bool
    cv_results: Optional[str] = None

    class Config:
        from_attributes = True


# ── Visit SKU Actions ────────────────────────────────────────────────────

class VisitSKUActionCreate(BaseModel):
    sku_id: int
    action_type: str  # gondola_llena | se_relleno | orden | unknown
    facings_count: Optional[int] = None
    notes: Optional[str] = None


class VisitSKUActionOut(BaseModel):
    id: int
    sku_id: int
    action_type: str
    facings_count: Optional[int] = None
    notes: Optional[str] = None
    sku: Optional[SKUOut] = None

    class Config:
        from_attributes = True


# ── Store Visits ─────────────────────────────────────────────────────────

class VisitStartRequest(BaseModel):
    """Step 1: Start visit - creates visit record."""
    store_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None


class VisitStartResponse(BaseModel):
    visit_id: int
    store_id: int
    start_time: datetime


class VisitConditionChecks(BaseModel):
    """Step 3: Condition check answers."""
    prices_on_gondola: bool
    pop_material_present: bool
    product_presentable: bool
    notes: Optional[str] = None


class VisitCompleteRequest(BaseModel):
    """Step 6: Complete/submit the visit."""
    # Condition checks
    prices_on_gondola: Optional[bool] = None
    pop_material_present: Optional[bool] = None
    product_presentable: Optional[bool] = None
    condition_notes: Optional[str] = None

    # SKU actions (all approved SKUs should have an action)
    sku_actions: list[VisitSKUActionCreate] = []

    notes: Optional[str] = None
    flags: Optional[str] = None  # JSON for any issues


class StoreVisitOut(BaseModel):
    id: int
    store_id: int
    user_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None

    prices_on_gondola: Optional[bool] = None
    pop_material_present: Optional[bool] = None
    product_presentable: Optional[bool] = None
    condition_notes: Optional[str] = None

    notes: Optional[str] = None
    status: str
    flags: Optional[str] = None
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
