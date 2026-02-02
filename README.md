# Ito Merchandising App

Shelf audit and store visit management for Ito merchandisers in Puerto Rico. Automates structured store-visit reporting with computer vision shelf analysis.

## Quick Start

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Seed the database with demo data
python -m backend.seed

# 4. Run the server
uvicorn backend.main:app --reload --port 8000
```

Open **http://localhost:8000** in a browser.

### Demo Accounts

| Username | Password  | Role         |
|----------|-----------|--------------|
| admin    | admin123  | Admin/President |
| merch1   | merch123  | Merchandiser |
| merch2   | merch123  | Merchandiser |

## Architecture

```
ITO-Project/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── database.py          # SQLite + SQLAlchemy setup
│   ├── models.py            # ORM models (Users, Stores, SKUs, Visits, Photos)
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── auth.py              # JWT auth with role-based access
│   ├── seed.py              # Demo data seeder
│   ├── routers/
│   │   ├── auth.py          # POST /api/auth/login, GET /api/auth/me
│   │   ├── stores.py        # CRUD /api/stores/
│   │   ├── skus.py          # CRUD /api/skus/
│   │   ├── approvals.py     # CRUD /api/approvals/
│   │   ├── visits.py        # POST /api/visits/, photo upload + CV
│   │   └── dashboard.py     # GET /api/dashboard/summary, by-store, incidents
│   └── cv/
│       └── void_detector.py # OpenCV shelf void detection (Stage A)
├── frontend/
│   ├── index.html           # Single-page app (mobile-first)
│   ├── css/style.css
│   └── js/
│       ├── api.js           # API client with JWT handling
│       └── app.js           # UI logic for visit, history, dashboard
├── uploads/                 # Uploaded shelf photos
├── requirements.txt
└── README.md
```

## Database Schema

```
users            (id, username, password_hash, full_name, role, region)
stores           (id, name, region, address, latitude, longitude)
skus             (id, name, brand, category, barcode)
store_sku_approvals (id, store_id, sku_id, quarter)
store_visits     (id, store_id, user_id, visited_at, lat, lng, notes, status)
visit_sku_actions (id, visit_id, sku_id, action_type, notes)
visit_photos     (id, visit_id, file_path, cv_processed, cv_results)
```

**action_type** values: `needs_refill` | `placed_on_shelf` | `needs_order`

## API Reference

### Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "merch1", "password": "merch123"}'

# Response:
# {"access_token": "...", "token_type": "bearer", "user_id": 2, "role": "merchandiser", "full_name": "Maria Santos"}
```

### Store Visit Submission

```bash
TOKEN="<access_token from login>"

# Create visit with SKU actions
curl -X POST http://localhost:8000/api/visits/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": 1,
    "latitude": 18.4571,
    "longitude": -66.0726,
    "notes": "Morning visit, shelves need restocking",
    "sku_actions": [
      {"sku_id": 1, "action_type": "needs_refill", "notes": "Only 2 left"},
      {"sku_id": 3, "action_type": "placed_on_shelf"},
      {"sku_id": 5, "action_type": "needs_order", "notes": "Warehouse empty"}
    ]
  }'

# Upload shelf photo (triggers CV analysis)
curl -X POST http://localhost:8000/api/visits/1/photos \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@shelf_photo.jpg"
```

### CV Inference Output Example

```json
{
  "void_space_score": 0.23,
  "void_regions": [
    {
      "bbox": {"x": 120, "y": 200, "w": 180, "h": 95},
      "confidence": 0.72
    },
    {
      "bbox": {"x": 450, "y": 310, "w": 140, "h": 95},
      "confidence": 0.61
    }
  ],
  "detected_products": [
    {
      "label": "product",
      "bbox": {"x": 30, "y": 210, "w": 55, "h": 80},
      "confidence": 0.65,
      "facings_count": 1
    }
  ],
  "image_width": 800,
  "image_height": 600
}
```

### Dashboard Endpoints

```bash
# Summary with filters
curl "http://localhost:8000/api/dashboard/summary?region=Metro&date_from=2026-01-01" \
  -H "Authorization: Bearer $TOKEN"

# By-store breakdown
curl "http://localhost:8000/api/dashboard/by-store?region=Metro" \
  -H "Authorization: Bearer $TOKEN"

# Unresolved incidents (>7 days = red severity)
curl "http://localhost:8000/api/dashboard/incidents?days_threshold=7" \
  -H "Authorization: Bearer $TOKEN"
```

## Computer Vision Approach

### Stage A — MVP (Current)

Uses OpenCV heuristics (no trained model required):

1. **Shelf line detection**: Canny edges + HoughLinesP to find horizontal shelf edges
2. **Void detection**: Each shelf strip is divided into columns; edge density + texture standard deviation identify empty regions
3. **Product detection**: Contour-based detection of rectangular product-like regions (placeholder — no SKU recognition)

### Stage B — Production Roadmap

**Model**: YOLOv8 or YOLOv9 fine-tuned for SKU detection

**Dataset preparation**:
```
dataset/
├── images/
│   ├── train/    # 70% — shelf photos from various stores/lighting
│   └── val/      # 30% — held-out validation set
├── labels/
│   ├── train/    # YOLO format: class_id cx cy w h (normalized)
│   └── val/
└── data.yaml     # class names, paths
```

**Labeling**: Use [Label Studio](https://labelstud.io/) or [Roboflow](https://roboflow.com/) for bounding box annotation. Label each SKU as a separate class.

**Training**:
```bash
pip install ultralytics
yolo detect train data=dataset/data.yaml model=yolov8m.pt epochs=100 imgsz=1280 batch=16
```

**Evaluation metrics**:
- mAP@0.5 for SKU detection (target: >0.7)
- Precision/recall for void detection
- Monitor false positive rate per store

**Active learning loop**:
1. Run inference on new shelf photos
2. Flag images where confidence < 0.4 (uncertain)
3. Send uncertain images to labeling queue
4. Retrain weekly with expanded dataset

**Deployment**:
```bash
# Export to ONNX for CPU inference
yolo export model=best.pt format=onnx

# Or serve with TorchServe / Triton for GPU inference
```

## MVP to Production Checklist

- [ ] **Auth**: Replace HMAC JWT with proper library (PyJWT) + bcrypt password hashing
- [ ] **Database**: Migrate from SQLite to PostgreSQL
- [ ] **File storage**: Replace local filesystem with S3 (abstract `StorageBackend` interface)
- [ ] **CV Model**: Train YOLOv8 on labeled shelf photos (Stage B)
- [ ] **Offline support**: Service worker + IndexedDB queue for low-connectivity submission
- [ ] **Photo compression**: Client-side resize to 1280px max before upload
- [ ] **Geofencing**: Validate merchandiser location is within 200m of store
- [ ] **Push notifications**: Alert admin when incidents age > 7 days
- [ ] **Audit trail**: Log all changes with timestamps and user IDs
- [ ] **Rate limiting**: Add API rate limits per user
- [ ] **HTTPS**: TLS termination via nginx or cloud load balancer
- [ ] **CI/CD**: Automated tests + deployment pipeline
- [ ] **Mobile app**: Wrap in Capacitor/React Native for native camera + GPS
