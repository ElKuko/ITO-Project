"""
Shelf void detection using classical computer vision (OpenCV).

Stage A MVP: Detects empty shelf regions using edge density analysis,
horizontal line detection (shelf edges), and texture analysis.

No ML model required — purely heuristic-based.
"""

import cv2
import numpy as np


def analyze_shelf_image(image_path: str) -> dict:
    """Analyze a shelf photo and return void detection results.

    Args:
        image_path: Path to the shelf image file.

    Returns:
        Dict with void_space_score, void_regions, detected_products,
        image_width, and image_height.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    height, width = img.shape[:2]

    # Resize for consistent processing (max 800px wide)
    scale = 1.0
    if width > 800:
        scale = 800 / width
        img = cv2.resize(img, (800, int(height * scale)))
        height, width = img.shape[:2]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ── Step 1: Detect shelf lines (horizontal edges) ─────────────────
    shelf_rows = _detect_shelf_lines(gray)

    # ── Step 2: Divide image into shelf regions ───────────────────────
    if len(shelf_rows) < 2:
        # If we can't find shelves, treat entire image as one region
        shelf_rows = [0, height]

    # ── Step 3: Analyze each shelf region for voids ───────────────────
    void_regions = []
    total_area = 0
    void_area = 0

    for i in range(len(shelf_rows) - 1):
        y_top = shelf_rows[i]
        y_bot = shelf_rows[i + 1]
        region_h = y_bot - y_top
        if region_h < 20:
            continue

        shelf_strip = gray[y_top:y_bot, :]
        region_voids = _find_void_regions_in_strip(shelf_strip, y_top, width, region_h)

        region_area = width * region_h
        total_area += region_area

        for v in region_voids:
            void_regions.append(v)
            void_area += v["bbox"]["w"] * v["bbox"]["h"]

    # ── Step 4: Detect product-like regions (occupied areas) ──────────
    detected_products = _detect_product_regions(gray, shelf_rows)

    # ── Step 5: Compute overall void score ────────────────────────────
    void_space_score = min(1.0, void_area / total_area) if total_area > 0 else 0.0

    # Scale bounding boxes back to original image coordinates
    if scale != 1.0:
        inv = 1.0 / scale
        for v in void_regions:
            v["bbox"] = {k: round(val * inv) for k, val in v["bbox"].items()}
        for p in detected_products:
            p["bbox"] = {k: round(val * inv) for k, val in p["bbox"].items()}
        width = round(width * inv)
        height = round(height * inv)

    return _sanitize({
        "void_space_score": round(float(void_space_score), 3),
        "void_regions": void_regions,
        "detected_products": detected_products,
        "image_width": int(width),
        "image_height": int(height),
    })


def _sanitize(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


def _detect_shelf_lines(gray: np.ndarray) -> list[int]:
    """Detect horizontal shelf lines using Canny + HoughLines."""
    edges = cv2.Canny(gray, 50, 150)
    # Strong horizontal kernel to emphasize shelf edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                            minLineLength=gray.shape[1] * 0.3, maxLineGap=20)

    h = gray.shape[0]
    shelf_ys = set()

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Only near-horizontal lines
            if abs(y2 - y1) < 10:
                avg_y = (y1 + y2) // 2
                shelf_ys.add(avg_y)

    # Cluster nearby y-values (within 15px)
    shelf_rows = sorted(shelf_ys)
    clustered = []
    for y in shelf_rows:
        if not clustered or y - clustered[-1] > 15:
            clustered.append(y)

    # Ensure top and bottom boundaries
    if not clustered or clustered[0] > 30:
        clustered.insert(0, 0)
    if not clustered or clustered[-1] < h - 30:
        clustered.append(h)

    return clustered


def _find_void_regions_in_strip(
    strip: np.ndarray, y_offset: int, width: int, region_h: int
) -> list[dict]:
    """Find empty regions within a single shelf strip using edge density."""
    voids = []
    # Divide strip into vertical columns
    col_width = max(40, width // 20)
    num_cols = width // col_width

    edges = cv2.Canny(strip, 30, 100)
    # Also compute local standard deviation as texture measure
    blur = cv2.GaussianBlur(strip, (5, 5), 0)

    empty_start = None
    for c in range(num_cols):
        x_start = c * col_width
        x_end = min(x_start + col_width, width)
        col_edges = edges[:, x_start:x_end]
        col_blur = blur[:, x_start:x_end]

        edge_density = np.count_nonzero(col_edges) / (col_edges.size + 1)
        texture_std = np.std(col_blur)

        # Low edge density AND low texture = likely empty
        is_empty = edge_density < 0.03 and texture_std < 25

        if is_empty:
            if empty_start is None:
                empty_start = x_start
        else:
            if empty_start is not None:
                void_w = x_start - empty_start
                if void_w >= col_width:  # Minimum void width
                    confidence = min(1.0, 0.5 + (void_w / width) * 0.5)
                    voids.append({
                        "bbox": {
                            "x": empty_start,
                            "y": y_offset,
                            "w": void_w,
                            "h": region_h,
                        },
                        "confidence": round(confidence, 2),
                    })
                empty_start = None

    # Handle void extending to right edge
    if empty_start is not None:
        void_w = width - empty_start
        if void_w >= col_width:
            confidence = min(1.0, 0.5 + (void_w / width) * 0.5)
            voids.append({
                "bbox": {
                    "x": empty_start,
                    "y": y_offset,
                    "w": void_w,
                    "h": region_h,
                },
                "confidence": round(confidence, 2),
            })

    return voids


def _detect_product_regions(gray: np.ndarray, shelf_rows: list[int]) -> list[dict]:
    """Detect product-like rectangular regions on shelves using contour detection.

    This is a placeholder approach. In production, use YOLOv8 trained on
    retail product datasets.
    """
    products = []
    edges = cv2.Canny(gray, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = (gray.shape[0] * gray.shape[1]) * 0.002  # 0.2% of image
    max_area = (gray.shape[0] * gray.shape[1]) * 0.15   # 15% of image

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = h / w if w > 0 else 0
        # Products tend to be taller than wide (bottles, boxes)
        if 0.3 < aspect < 5.0:
            products.append({
                "label": "product",  # Generic label — no SKU recognition in MVP
                "bbox": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                "confidence": round(min(0.8, 0.3 + (area / max_area) * 0.5), 2),
                "facings_count": 1,
            })

    # Limit to top 50 detections by confidence
    products.sort(key=lambda p: p["confidence"], reverse=True)
    return products[:50]
