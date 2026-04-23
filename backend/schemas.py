"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


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
    role: str = "merchandiser"  # merchandiser | supervisor | admin
    region: Optional[str] = None


class UserUpdate(BaseModel):
    """Update user - all fields optional."""
    full_name: Optional[str] = None
    role: Optional[str] = None  # merchandiser | supervisor | admin
    region: Optional[str] = None
    password: Optional[str] = None  # If provided, will update password
    is_active: Optional[bool] = None


# ── Stores ────────────────────────────────────────────────────────────────

class StoreCreate(BaseModel):
    name: str
    chain: Optional[str] = None  # e.g., "Pueblo", "Econo", "Selectos"
    region: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None


class StoreOut(BaseModel):
    id: int
    name: str
    chain: Optional[str] = None
    region: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


# ── SKUs ──────────────────────────────────────────────────────────────────

class SKUCreate(BaseModel):
    name: str
    brand: str
    category: Optional[str] = None
    section: Optional[str] = None  # produce | provisiones | congelados
    barcode: Optional[str] = None
    image_url: Optional[str] = None


class SKUOut(BaseModel):
    id: int
    name: str
    brand: str
    category: Optional[str] = None
    section: Optional[str] = None  # produce | provisiones | congelados
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
    photo_type: str  # arrival_proof | gondola_before | gondola_after
    gondola_group_id: Optional[str] = None  # UUID linking before/after photos
    sku_ids: list[int] = []  # SKUs this photo represents
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    captured_at: Optional[datetime] = None


class PhotoSKULinkOut(BaseModel):
    sku_id: int
    sku: Optional[SKUOut] = None

    class Config:
        from_attributes = True


class VisitPhotoOut(BaseModel):
    id: int
    photo_type: str
    file_path: str
    gondola_group_id: Optional[str] = None
    captured_at: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    cv_processed: bool
    cv_results: Optional[str] = None
    sku_links: list[PhotoSKULinkOut] = []

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
    gondola_space_gained: Optional[bool] = None
    notes: Optional[str] = None


class VisitCompleteRequest(BaseModel):
    """Step 5: Complete/submit the visit."""
    # Per-section condition checks (new format)
    # Format: {"produce": {"prices": true, "pop": true, "presentable": true, "notes": ""}, ...}
    section_conditions: Optional[dict] = None

    # Legacy condition checks (for backwards compatibility)
    prices_on_gondola: Optional[bool] = None
    pop_material_present: Optional[bool] = None
    product_presentable: Optional[bool] = None
    gondola_space_gained: Optional[bool] = None
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
    gondola_space_gained: Optional[bool] = None
    condition_notes: Optional[str] = None
    section_conditions: Optional[str] = None  # JSON string

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


# ── Notifications ─────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    """Notification response for admin console."""
    id: int
    event_type: str  # visit_completed | photos_submitted | visit_started | issue_flagged
    route_id: Optional[int] = None
    route_name: Optional[str] = None
    visit_id: int
    store_id: int
    store_name: str
    merchandiser_id: int
    merchandiser_name: str
    summary_data: Optional[str] = None  # JSON string with counts
    event_time: datetime
    created_at: datetime
    is_read: bool
    read_at: Optional[datetime] = None
    is_acknowledged: bool
    acknowledged_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    """Internal schema for creating notifications."""
    event_type: str
    route_id: Optional[int] = None
    route_name: Optional[str] = None
    visit_id: int
    store_id: int
    store_name: str
    merchandiser_id: int
    merchandiser_name: str
    summary_data: Optional[str] = None
    event_time: datetime


class NotificationMarkRead(BaseModel):
    """Mark notifications as read."""
    notification_ids: list[int]


class NotificationMarkAcknowledged(BaseModel):
    """Mark notifications as acknowledged."""
    notification_ids: list[int]


class NotificationFilters(BaseModel):
    """Filters for querying notifications."""
    route_id: Optional[int] = None
    event_type: Optional[str] = None
    is_read: Optional[bool] = None
    is_acknowledged: Optional[bool] = None
    since_id: Optional[int] = None  # For pagination/reconnection
    since_time: Optional[datetime] = None  # For sync after disconnect
    limit: int = 50


class NotificationCountOut(BaseModel):
    """Unread notification counts per route."""
    route_id: Optional[int] = None
    route_name: Optional[str] = None
    unread_count: int
    total_count: int


class WebSocketMessage(BaseModel):
    """Message format for WebSocket communication."""
    type: str  # notification | sync | ack | error
    data: Optional[dict] = None


# ── Route Chat ───────────────────────────────────────────────────────────

class TaggedReference(BaseModel):
    """Reference to a specific visit photo for tagged messages."""
    visit_id: int
    store_id: int
    store_name: str
    photo_id: int
    photo_type: str  # BEFORE | AFTER
    gondola_group_id: Optional[str] = None
    photo_url: Optional[str] = None
    captured_at: Optional[datetime] = None


class ChatMessageCreate(BaseModel):
    """Create a new chat message."""
    route_id: int
    text: str
    message_type: str = "TEXT"  # TEXT | TAGGED_REFERENCE | ANNOTATED_REFERENCE
    reference: Optional[TaggedReference] = None
    annotated_reference: Optional["AnnotatedReference"] = None


class ChatMessageOut(BaseModel):
    """Chat message response."""
    id: int
    route_id: int
    sender_user_id: int
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    message_type: str
    text: str

    # Reference fields (for TAGGED_REFERENCE)
    ref_visit_id: Optional[int] = None
    ref_store_id: Optional[int] = None
    ref_store_name: Optional[str] = None
    ref_photo_id: Optional[int] = None
    ref_photo_type: Optional[str] = None
    ref_gondola_group_id: Optional[str] = None
    ref_photo_url: Optional[str] = None
    ref_captured_at: Optional[datetime] = None

    # Annotation reference fields (for ANNOTATED_REFERENCE)
    ref_annotation_id: Optional[int] = None
    ref_annotation_preview_url: Optional[str] = None

    created_at: datetime
    is_read: bool

    class Config:
        from_attributes = True


class ChatMessageMarkRead(BaseModel):
    """Mark chat messages as read."""
    message_ids: list[int]


# ── Image Annotations ────────────────────────────────────────────────────

class AnnotationCreate(BaseModel):
    """Create an annotation on a visit photo."""
    photo_id: int
    visit_id: int
    photo_type: str  # BEFORE | AFTER
    gondola_group_id: Optional[str] = None
    annotation_data: str  # JSON array of drawing objects


class AnnotationOut(BaseModel):
    """Annotation response."""
    id: int
    photo_id: int
    visit_id: int
    photo_type: str
    gondola_group_id: Optional[str] = None
    annotation_data: str  # JSON array of drawing objects
    preview_path: Optional[str] = None
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class AnnotatedReference(BaseModel):
    """Reference to an annotated photo for chat messages."""
    annotation_id: int
    visit_id: int
    store_id: int
    store_name: str
    photo_id: int
    photo_type: str  # BEFORE | AFTER
    gondola_group_id: Optional[str] = None
    original_photo_url: Optional[str] = None
    annotation_preview_url: Optional[str] = None
    captured_at: Optional[datetime] = None


# ── Work Items (New Workflow) ────────────────────────────────────────────

class WorkItemCreate(BaseModel):
    """Create a work item from a photo."""
    segment: str  # produce | provisiones | congelados
    photo_id: int  # The before photo that creates this work item


class WorkItemSKUAction(BaseModel):
    """SKU action within a work item."""
    sku_id: int
    estado_gondola: Optional[str] = None  # llena | semi | agotada
    trabajo: list[str] = []  # list of: organice | rellene | ordene
    orden_cantidad_cajas: Optional[int] = None  # Optional, used with ordene
    orden_fecha_llegada: Optional[datetime] = None  # Optional, used with ordene
    notes: Optional[str] = None


class WorkItemUpdate(BaseModel):
    """Update a work item with SKU actions and condition checks."""
    sku_actions: list[WorkItemSKUAction] = []
    prices_on_gondola: Optional[bool] = None
    pop_material_present: Optional[bool] = None
    product_presentable: Optional[bool] = None
    gondola_space_gained: Optional[bool] = None
    condition_notes: Optional[str] = None


class WorkItemComplete(BaseModel):
    """Complete a work item by adding the after photo."""
    after_photo_id: int


class WorkItemSKUActionOut(BaseModel):
    """SKU action output within a work item."""
    id: int
    sku_id: int
    estado_gondola: Optional[str] = None
    trabajo: Optional[list[str]] = None
    orden_cantidad_cajas: Optional[int] = None
    orden_fecha_llegada: Optional[datetime] = None
    notes: Optional[str] = None
    sku: Optional[SKUOut] = None

    @field_validator("trabajo", mode="before")
    @classmethod
    def parse_trabajo(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return v
        return v.split(",")

    class Config:
        from_attributes = True


class WorkItemOut(BaseModel):
    """Work item response."""
    id: int
    visit_id: int
    segment: str
    status: str  # created | in_progress | completed
    before_photo_id: Optional[int] = None
    after_photo_id: Optional[int] = None
    before_photo: Optional[VisitPhotoOut] = None
    after_photo: Optional[VisitPhotoOut] = None
    sku_actions: list[WorkItemSKUActionOut] = []
    prices_on_gondola: Optional[bool] = None
    pop_material_present: Optional[bool] = None
    product_presentable: Optional[bool] = None
    gondola_space_gained: Optional[bool] = None
    condition_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SegmentAvailableSKUs(BaseModel):
    """Available SKUs for a segment (excluding already assigned ones)."""
    segment: str
    skus: list[SKUOut]
    assigned_sku_ids: list[int]  # SKUs already assigned to other work items


class SegmentSummary(BaseModel):
    """Summary of work items in a segment."""
    segment: str
    total_work_items: int
    completed_work_items: int
    pending_work_items: int
    in_progress_work_items: int
