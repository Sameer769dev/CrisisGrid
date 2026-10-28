"""Deterministic corridor / landing-zone verifier - Day 4 (Oct 30, 2026).

Trust layer (AGENTS.md SS4 + SS6, binding):
- ALL geometry in this module is pure, deterministic, local Python.
  NO model call exists inside any geometry function.
- sam-3.1 hazard/safe detections (Day 2) are checked against candidate
  corridors / landing zones that muse-spark-1.3 proposed (Day 3):
    * corridor: fraction of route length intersecting hazard masks/boxes
      (rejected when > 10%), hazard footprint IoU, safe-infrastructure
      support fraction along the route;
    * landing zone: hazard overlap fraction + box/mask IoU, safe-surface
      support, and minimum clearance area (drone / helicopter).
- Mask IoU is computed exactly when a SAM RLE payload decodes with one of
  the supported deterministic decoders; otherwise the verifier falls back
  to exact bounding-box geometry and says so in the trace.
- Only candidates this module marks "verified" may flow to Day 5 dispatch.
- The muse-spark-1.3 self-correction loop lives OUTSIDE the geometry:
  verify -> (rejected?) -> Spark re-route -> verify again, bounded.
- OpenStreetMap Overpass (free, AGENTS.md SS2) supplies nearby emergency
  facilities when geographic coordinates are supplied. Image-normalized
  candidates are NOT GPS coordinates, so facilities are contextual only.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import time
from typing import Any, Callable, Iterable

import httpx

try:  # repo-root imports (uvicorn backend.main:app)
    from backend.config import get_async_meta_client
    from backend.services.sam_hazard_scanner import extract_output_text
    from backend.services.voice_and_triage import (
        TRIAGE_MODEL,
        normalize_assessment,
        parse_spark_triage,
        summarize_scan,
    )
except ImportError:  # backend/ imports (uvicorn main:app, tests)
    from config import get_async_meta_client
    from services.sam_hazard_scanner import extract_output_text
    from services.voice_and_triage import (
        TRIAGE_MODEL,
        normalize_assessment,
        parse_spark_triage,
        summarize_scan,
    )

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
CORRECTION_MODEL = TRIAGE_MODEL  # muse-spark-1.3 re-routes its own proposals

DEFAULT_MAX_HAZARD_INTERSECTION = 0.10  # >10% hazard contact forces re-route
DEFAULT_MIN_SAFE_SUPPORT = 0.50
DEFAULT_MIN_SAFE_SURFACE_OVERLAP = 0.50
DEFAULT_CORRIDOR_BUFFER_NORM = 0.01
# Minimum effective landing radius as fraction of the image short side.
# (No GPS scale exists in an image, so clearance is certified in image
# space and reported in pixels - never converted to fake metres.)
MIN_LANDING_RADIUS_NORM = {"drone": 0.015, "helicopter": 0.04}

VERIFIED_COLOR = "#00C853"   # AGENTS.md SS6: green only when verified here
REJECTED_COLOR = "#FF2D20"   # red: hazard / blocked
UNVERIFIED_COLOR = "#FFD600"  # yellow: proposal not yet checked

HAZARD_CONCEPTS_SET = {"flood water", "debris", "fire", "damaged building", "stranded vehicle"}
SAFE_CONCEPTS_SET = {"road", "bridge", "clear flat ground", "rooftop"}


class MaskDecodeError(ValueError):
    """A SAM mask payload could not be decoded by any supported decoder."""


# --------------------------------------------------------------------------- #
# Basic rectangle geometry (normalized image coordinates unless stated)
# --------------------------------------------------------------------------- #
Box = tuple[float, float, float, float]  # (x1, y1, x2, y2)
Point = tuple[float, float]


def clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def make_box(x1: float, y1: float, x2: float, y2: float) -> Box:
    return (round(clamp01(min(x1, x2)), 6), round(clamp01(min(y1, y2)), 6),
            round(clamp01(max(x1, x2)), 6), round(clamp01(max(y1, y2)), 6))


def box_area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def box_intersection_area(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def box_iou(a: Box, b: Box) -> float:
    """Intersection-over-Union of two normalized boxes. Pure geometry."""
    inter = box_intersection_area(a, b)
    union = box_area(a) + box_area(b) - inter
    return round(inter / union, 6) if union > 0 else 0.0


def rect_union_area(boxes: Iterable[Box], clip: Box | None = None) -> float:
    """Exact union area of rectangles (optionally clipped) via x-sweep."""
    rects = []
    for box in boxes:
        b = box
        if clip is not None:
            b = (max(b[0], clip[0]), max(b[1], clip[1]), min(b[2], clip[2]), min(b[3], clip[3]))
        if b[2] > b[0] and b[3] > b[1]:
            rects.append(b)
    if not rects:
        return 0.0
    xs = sorted({b[0] for b in rects} | {b[2] for b in rects})
    area = 0.0
    for x_lo, x_hi in zip(xs, xs[1:]):
        if x_hi <= x_lo:
            continue
        spans = sorted((b[1], b[3]) for b in rects if b[0] <= x_lo and b[2] >= x_hi)
        covered, cur_lo, cur_hi = 0.0, None, None
        for lo, hi in spans:
            if cur_lo is None:
                cur_lo, cur_hi = lo, hi
            elif lo <= cur_hi:
                cur_hi = max(cur_hi, hi)
            else:
                covered += cur_hi - cur_lo
                cur_lo, cur_hi = lo, hi
        if cur_lo is not None:
            covered += cur_hi - cur_lo
        area += (x_hi - x_lo) * covered
    return area


# --------------------------------------------------------------------------- #
# Polyline geometry
# --------------------------------------------------------------------------- #
def _segment_rect_interval(p: Point, q: Point, box: Box) -> tuple[float, float] | None:
    """Liang-Barsky: parameter interval of segment p->q inside a rectangle."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    t_lo, t_hi = 0.0, 1.0
    for p_val, q_val in ((-dx, p[0] - box[0]), (dx, box[2] - p[0]),
                         (-dy, p[1] - box[1]), (dy, box[3] - p[1])):
        if abs(p_val) < 1e-12:
            if q_val < 0:
                return None
            continue
        t = q_val / p_val
        if p_val < 0:
            t_lo = max(t_lo, t)
        else:
            t_hi = min(t_hi, t)
        if t_lo > t_hi:
            return None
    return (t_lo, t_hi) if t_hi >= t_lo else None


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for lo, hi in sorted(intervals):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def polyline_length(points: list[Point]) -> float:
    return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(points, points[1:]))


def polyline_box_fraction(points: list[Point], boxes: list[Box]) -> float:
    """Fraction of total polyline length inside the UNION of boxes (exact)."""
    total = polyline_length(points)
    if total <= 0 or not boxes:
        return 0.0
    inside = 0.0
    for p, q in zip(points, points[1:]):
        seg_len = math.hypot(q[0] - p[0], q[1] - p[1])
        if seg_len <= 0:
            continue
        intervals = [iv for box in boxes if (iv := _segment_rect_interval(p, q, box)) is not None]
        inside += seg_len * sum(hi - lo for lo, hi in _merge_intervals(intervals))
    return round(min(1.0, inside / total), 6)

# --------------------------------------------------------------------------- #
# SAM RLE mask decoding (deterministic; standard formats only)
# --------------------------------------------------------------------------- #
def _grid_from_counts(counts: list[int], width: int, height: int, *, column_major: bool) -> bytearray:
    total = width * height
    if sum(counts) != total:
        raise MaskDecodeError(f"RLE counts sum {sum(counts)} != mask pixels {total}")
    grid = bytearray(total)
    value, pos = 0, 0
    for count in counts:
        if value == 1 and count:
            if column_major:
                for k in range(pos, pos + count):
                    x, y = divmod(k, height)
                    grid[y * width + x] = 1
            else:
                grid[pos:pos + count] = b"\x01" * count
        pos += count
        value = 1 - value
    return grid


def _decode_coco_counts(data: str) -> list[int]:
    """Decode COCO's compressed RLE count string (pycocotools format)."""
    counts: list[int] = []
    pos, m = 0, len(data)
    while pos < m:
        value, shift = 0, 0
        while True:
            if pos >= m:
                raise MaskDecodeError("Truncated COCO RLE string")
            k = ord(data[pos]) - 48
            pos += 1
            value |= (k & 0x1F) << shift
            shift += 5
            if not (k & 0x20):
                if k & 0x10:
                    value |= -1 << shift
                break
            if shift > 60:
                raise MaskDecodeError("COCO RLE count overflow")
        if len(counts) > 2:
            value += counts[-2]
        counts.append(value)
    return counts


_INT_LIST_RE = re.compile(r"^[\d\s,;:]+$")


def decode_sam_mask(mask: dict[str, Any] | None, *, image_width: int, image_height: int) -> tuple[bytearray, int, int]:
    """Decode a SAM mask payload to a row-major 0/1 grid (full image space).

    Supported deterministic formats: integer run-length counts (row-major or
    COCO column-major), COCO compressed RLE strings, and the explicit fixture
    format "counts:<n0,n1,...>". Anything else (including opaque vendor
    encodings) raises MaskDecodeError and the verifier falls back to
    bounding boxes - loudly, in the trace.
    """
    if not mask or not mask.get("data"):
        raise MaskDecodeError("Detection carries no mask payload")
    data = str(mask["data"]).strip()
    width = int(mask.get("width") or image_width)
    height = int(mask.get("height") or image_height)
    if width <= 0 or height <= 0:
        raise MaskDecodeError("Mask declares non-positive dimensions")
    off_x, off_y = int(mask.get("x") or 0), int(mask.get("y") or 0)

    counts: list[int] | None = None
    if data.lower().startswith("counts:"):
        counts = [int(v) for v in re.findall(r"\d+", data[7:])]
    elif _INT_LIST_RE.match(data):
        counts = [int(v) for v in re.findall(r"\d+", data)]
    if counts is not None:
        local = None
        for col_major in (False, True):
            try:
                local = _grid_from_counts(counts, width, height, column_major=col_major)
                break
            except MaskDecodeError:
                continue
        if local is None:
            raise MaskDecodeError("Integer RLE counts do not sum to mask size")
    else:
        try:
            coco_counts = _decode_coco_counts(data)
            local = _grid_from_counts(coco_counts, width, height, column_major=True)
        except (MaskDecodeError, ValueError, IndexError) as exc:
            raise MaskDecodeError(
                "Mask payload is not a supported RLE format "
                "(integer counts / COCO string); bounding-box geometry will be used") from exc

    if (off_x, off_y) == (0, 0) and (width, height) == (image_width, image_height):
        return local, width, height
    full = bytearray(image_width * image_height)
    for y in range(height):
        ty = off_y + y
        if 0 <= ty < image_height:
            src = local[y * width:(y + 1) * width]
            dst_x, src_x = max(0, off_x), max(0, -off_x)
            run = min(width - src_x, image_width - dst_x)
            if run > 0:
                full[ty * image_width + dst_x: ty * image_width + dst_x + run] = src[src_x:src_x + run]
    return full, image_width, image_height


def encode_counts_fixture(grid: list[list[int]]) -> str:
    """Encode a 0/1 grid as 'counts:...' row-major RLE (tests/fixtures)."""
    flat = [v for row in grid for v in row]
    counts: list[int] = []
    value, run = 0, 0
    for v in flat:
        if v == value:
            run += 1
        else:
            counts.append(run)
            value, run = v, 1
    counts.append(run)
    return "counts:" + ",".join(str(c) for c in counts)


# --------------------------------------------------------------------------- #
# Scan field construction (hazards / safe infrastructure, boxes + masks)
# --------------------------------------------------------------------------- #
def _detection_box(det: dict[str, Any], image_w: int, image_h: int) -> Box | None:
    if det.get("bbox_xyxy_norm"):
        v = det["bbox_xyxy_norm"]
        return make_box(float(v[0]), float(v[1]), float(v[2]), float(v[3]))
    if isinstance(det.get("bbox"), dict):
        b = det["bbox"]
        return make_box(float(b["x_min"]), float(b["y_min"]), float(b["x_max"]), float(b["y_max"]))
    if isinstance(det.get("bbox_px"), dict) and image_w > 0 and image_h > 0:
        b = det["bbox_px"]
        return make_box(b["x1"] / image_w, b["y1"] / image_h, b["x2"] / image_w, b["y2"] / image_h)
    return None


def extract_scan_detections(scan_result: dict[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
    """Flatten a Day 2 scan into detections + image size (boxes normalised)."""
    image = scan_result.get("image") or {}
    image_w, image_h = int(image.get("width") or 0), int(image.get("height") or 0)
    raw: list[dict[str, Any]] = list(scan_result.get("detections") or [])
    if not raw:
        for layer in scan_result.get("concept_layers") or []:
            for det in layer.get("detections") or []:
                raw.append({**det, "concept": det.get("concept") or layer.get("concept"),
                            "kind": det.get("kind") or layer.get("kind")})
    detections: list[dict[str, Any]] = []
    for det in raw:
        concept = str(det.get("concept") or "unknown")
        kind = str(det.get("kind") or "").lower()
        if kind not in ("hazard", "safe_zone"):
            kind = "hazard" if concept in HAZARD_CONCEPTS_SET else (
                "safe_zone" if concept in SAFE_CONCEPTS_SET else "custom")
        box = _detection_box(det, image_w, image_h)
        if box is None:
            continue
        detections.append({"concept": concept, "kind": kind, "box": box,
                           "mask": det.get("mask"), "has_mask": bool(det.get("has_mask") or det.get("mask"))})
    if (image_w <= 0 or image_h <= 0) and detections:
        for det in detections:
            mask = det.get("mask") or {}
            if mask.get("width") and mask.get("height"):
                image_w, image_h = int(mask["width"]), int(mask["height"])
                break
    return detections, image_w, image_h


class DetectionField:
    """Precomputed hazard/safe geometry: box lists + optional mask unions."""

    def __init__(self, detections: list[dict[str, Any]], image_w: int, image_h: int):
        self.image_w, self.image_h = image_w, image_h
        self.hazards = [d for d in detections if d["kind"] == "hazard"]
        self.safe = [d for d in detections if d["kind"] == "safe_zone"]
        self.hazard_boxes = [d["box"] for d in self.hazards]
        self.safe_boxes = [d["box"] for d in self.safe]
        self.mask_decoded = 0
        self.mask_total = 0
        self.mask_errors: list[str] = []
        self.hazard_mask = self._build_union(self.hazards)
        self.safe_mask = self._build_union(self.safe)

    def _build_union(self, dets: list[dict[str, Any]]) -> bytearray | None:
        if self.image_w <= 0 or self.image_h <= 0:
            return None
        union: bytearray | None = None
        for det in dets:
            if not det.get("mask"):
                continue
            self.mask_total += 1
            try:
                grid, _, _ = decode_sam_mask(det["mask"], image_width=self.image_w, image_height=self.image_h)
            except MaskDecodeError as exc:
                if len(self.mask_errors) < 3:
                    self.mask_errors.append(f"{det['concept']}: {exc}")
                continue
            self.mask_decoded += 1
            if union is None:
                union = bytearray(grid)
            else:
                for i, v in enumerate(grid):
                    if v:
                        union[i] = 1
        return union

    @property
    def method(self) -> str:
        """'mask' only when every mask-bearing detection decoded."""
        return "mask" if (self.mask_total and self.mask_decoded == self.mask_total) else "bbox"

    def _px(self, point: Point) -> tuple[int, int]:
        return (min(self.image_w - 1, max(0, int(point[0] * self.image_w))),
                min(self.image_h - 1, max(0, int(point[1] * self.image_h))))

    def sample_polyline(self, points: list[Point], step_px: float = 1.0) -> list[tuple[int, int]]:
        samples: list[tuple[int, int]] = []
        for p, q in zip(points, points[1:]):
            ppx = (p[0] * self.image_w, p[1] * self.image_h)
            qpx = (q[0] * self.image_w, q[1] * self.image_h)
            steps = max(1, int(math.hypot(qpx[0] - ppx[0], qpx[1] - ppx[1]) / step_px))
            for i in range(steps + 1):
                t = i / steps
                samples.append(self._px((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)))
        return samples

    def mask_fraction_polyline(self, points: list[Point], grid: bytearray) -> float:
        samples = self.sample_polyline(points)
        if not samples:
            return 0.0
        inside = sum(1 for x, y in samples if grid[y * self.image_w + x])
        return round(inside / len(samples), 6)

    def mask_pixels(self, grid: bytearray | None) -> set[int]:
        return {i for i, v in enumerate(grid) if v} if grid is not None else set()

    def rasterize_polyline(self, points: list[Point], buffer_px: float) -> set[int]:
        pixels: set[int] = set()
        radius = max(0, int(buffer_px))
        for x, y in self.sample_polyline(points):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx * dx + dy * dy <= radius * radius:
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < self.image_w and 0 <= yy < self.image_h:
                            pixels.add(yy * self.image_w + xx)
        return pixels

    def rasterize_circle(self, center: Point, radius_norm: float) -> set[int]:
        cx, cy = center[0] * self.image_w, center[1] * self.image_h
        rx, ry = radius_norm * self.image_w, radius_norm * self.image_h
        pixels: set[int] = set()
        for yy in range(max(0, int(cy - ry)), min(self.image_h, int(cy + ry) + 1)):
            for xx in range(max(0, int(cx - rx)), min(self.image_w, int(cx + rx) + 1)):
                if ((xx - cx) / max(rx, 1e-9)) ** 2 + ((yy - cy) / max(ry, 1e-9)) ** 2 <= 1.0:
                    pixels.add(yy * self.image_w + xx)
        return pixels

# --------------------------------------------------------------------------- #
# Candidate extraction / normalisation (Day 3 output shapes)
# --------------------------------------------------------------------------- #
def _norm_point(raw: Any) -> Point | None:
    try:
        if isinstance(raw, dict):
            return (clamp01(float(raw["x"])), clamp01(float(raw["y"])))
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            return (clamp01(float(raw[0])), clamp01(float(raw[1])))
    except (KeyError, TypeError, ValueError):
        return None
    return None


def extract_candidates(
    triage_result: dict[str, Any] | None = None,
    corridors: list[dict[str, Any]] | None = None,
    landing_zones: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pull candidate corridors/zones from explicit args or a Day 3 payload."""
    src: dict[str, Any] = triage_result or {}
    nested = src.get("triage") if isinstance(src.get("triage"), dict) else {}
    corr_raw = corridors if corridors is not None else (
        src.get("candidate_evacuation_corridors") or nested.get("candidate_evacuation_corridors") or [])
    zone_raw = landing_zones if landing_zones is not None else (
        src.get("candidate_landing_zones") or nested.get("candidate_landing_zones") or [])

    norm_corridors: list[dict[str, Any]] = []
    for i, cand in enumerate(corr_raw, start=1):
        points = [p for p in (_norm_point(pt) for pt in cand.get("points_norm") or []) if p]
        norm_corridors.append({
            "id": str(cand.get("id") or f"corridor-{i}"), "name": str(cand.get("name") or ""),
            "purpose": str(cand.get("purpose") or "evacuation"),
            "points_norm": [{"x": x, "y": y} for x, y in points], "points": points,
            "start_label": str(cand.get("start_label") or ""), "end_label": str(cand.get("end_label") or ""),
            "rationale": str(cand.get("rationale") or ""),
            "grounded_concepts": list(cand.get("grounded_concepts") or []),
            "source_status": str(cand.get("status") or "unverified_candidate"),
        })
    norm_zones: list[dict[str, Any]] = []
    for i, cand in enumerate(zone_raw, start=1):
        center = _norm_point(cand.get("center_norm")) or (0.5, 0.5)
        try:
            radius = float(cand.get("radius_norm") or 0.0)
        except (TypeError, ValueError):
            radius = 0.0
        norm_zones.append({
            "id": str(cand.get("id") or f"landing-zone-{i}"), "name": str(cand.get("name") or ""),
            "center_norm": {"x": center[0], "y": center[1]}, "center": center,
            "radius_norm": min(0.5, max(0.0, radius)),
            "surface_concept": str(cand.get("surface_concept") or ""),
            "zone_type": str(cand.get("zone_type") or cand.get("aircraft_type") or ""),
            "rationale": str(cand.get("rationale") or ""),
            "grounded_concepts": list(cand.get("grounded_concepts") or []),
            "source_status": str(cand.get("status") or "unverified_candidate"),
        })
    return norm_corridors, norm_zones


def _corridor_footprint_box(points: list[Point], buffer_norm: float) -> Box:
    xs = [p[0] for p in points] or [0.0]
    ys = [p[1] for p in points] or [0.0]
    return make_box(min(xs) - buffer_norm, min(ys) - buffer_norm,
                    max(xs) + buffer_norm, max(ys) + buffer_norm)


# --------------------------------------------------------------------------- #
# Deterministic verification (NO model calls in this section)
# --------------------------------------------------------------------------- #
def verify_corridor(
    candidate: dict[str, Any], field: DetectionField, *,
    max_hazard_intersection: float = DEFAULT_MAX_HAZARD_INTERSECTION,
    min_safe_support: float = DEFAULT_MIN_SAFE_SUPPORT,
    require_safe_support: bool = True,
    corridor_buffer_norm: float = DEFAULT_CORRIDOR_BUFFER_NORM,
) -> dict[str, Any]:
    points: list[Point] = candidate["points"]
    reasons: list[str] = []
    use_mask = field.method == "mask" and field.hazard_mask is not None
    total_len_px = polyline_length([(x * field.image_w, y * field.image_h) for x, y in points]) \
        if field.image_w > 0 else polyline_length(points)
    footprint_box = _corridor_footprint_box(points, corridor_buffer_norm)

    if len(points) < 2 or total_len_px <= 0:
        hazard_ratio, safe_ratio, footprint_iou = 1.0, 0.0, 0.0
        reasons.append("Corridor has fewer than 2 distinct points (zero length).")
        per_hazard: list[dict[str, Any]] = []
    elif use_mask:
        hazard_ratio = field.mask_fraction_polyline(points, field.hazard_mask)  # type: ignore[arg-type]
        safe_ratio = field.mask_fraction_polyline(points, field.safe_mask) if field.safe_mask is not None else 0.0
        footprint = field.rasterize_polyline(points, corridor_buffer_norm * min(field.image_w, field.image_h))
        hazard_px = field.mask_pixels(field.hazard_mask)
        inter = len(footprint & hazard_px)
        footprint_iou = round(inter / len(footprint | hazard_px), 6) if footprint | hazard_px else 0.0
        per_hazard = [{"concept": det["concept"], "box_intersection_ratio": ratio,
                       "box_iou": box_iou(footprint_box, det["box"])}
                      for det in field.hazards
                      if (ratio := polyline_box_fraction(points, [det["box"]])) > 0]
    else:
        hazard_ratio = polyline_box_fraction(points, field.hazard_boxes)
        safe_ratio = polyline_box_fraction(points, field.safe_boxes)
        footprint_iou = max((box_iou(footprint_box, b) for b in field.hazard_boxes), default=0.0)
        per_hazard = [{"concept": det["concept"], "box_intersection_ratio": ratio,
                       "box_iou": box_iou(footprint_box, det["box"])}
                      for det in field.hazards
                      if (ratio := polyline_box_fraction(points, [det["box"]])) > 0]

    if len(points) >= 2 and total_len_px > 0:
        if hazard_ratio > max_hazard_intersection:
            reasons.append(
                f"Hazard intersection {hazard_ratio:.1%} exceeds {max_hazard_intersection:.0%} threshold "
                f"({', '.join(h['concept'] for h in per_hazard) or 'hazard mask'}).")
        if require_safe_support and field.safe_boxes:
            if safe_ratio < min_safe_support:
                reasons.append(
                    f"Only {safe_ratio:.1%} of route lies on segmented safe infrastructure "
                    f"(< {min_safe_support:.0%} required: road/bridge/clear ground/rooftop).")
        elif require_safe_support and not field.safe_boxes:
            reasons.append("No safe infrastructure was segmented, so route support cannot be confirmed.")

    verified = not reasons
    return {
        "candidate_id": candidate["id"], "kind": "evacuation_corridor",
        "candidate": {k: v for k, v in candidate.items() if k != "points"},
        "status": "verified" if verified else "rejected",
        "color": VERIFIED_COLOR if verified else REJECTED_COLOR,
        "method": "mask" if use_mask else "bbox",
        "hazard_intersection_ratio": hazard_ratio, "hazard_threshold": max_hazard_intersection,
        "hazard_footprint_iou": footprint_iou,
        "safe_support_ratio": safe_ratio,
        "min_safe_support": min_safe_support if require_safe_support else None,
        "route_length_px": round(total_len_px, 1) if field.image_w > 0 else None,
        "route_length_norm": round(polyline_length(points), 6),
        "intersecting_hazards": per_hazard,
        "reasons": reasons or ["Hazard intersection within threshold and route follows segmented safe infrastructure."],
        "requires_reroute": not verified,
    }


def verify_landing_zone(
    candidate: dict[str, Any], field: DetectionField, *,
    max_hazard_intersection: float = DEFAULT_MAX_HAZARD_INTERSECTION,
    min_safe_surface_overlap: float = DEFAULT_MIN_SAFE_SURFACE_OVERLAP,
    default_zone_kind: str = "drone",
) -> dict[str, Any]:
    center: Point = candidate["center"]
    radius = candidate["radius_norm"]
    reasons: list[str] = []
    zone_box = make_box(center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    use_mask = field.method == "mask" and field.hazard_mask is not None
    kind_text = " ".join([candidate.get("zone_type", ""), candidate.get("name", ""),
                          candidate.get("surface_concept", ""), candidate.get("rationale", "")]).lower()
    zone_kind = "helicopter" if ("helicopter" in kind_text or "helipad" in kind_text or "heli " in kind_text) \
        else ("drone" if "drone" in kind_text else default_zone_kind)

    if field.image_w > 0 and field.image_h > 0:
        radius_x_px, radius_y_px = radius * field.image_w, radius * field.image_h
        effective_radius_px = min(radius_x_px, radius_y_px)
        clearance = {
            "radius_x_px": round(radius_x_px, 1), "radius_y_px": round(radius_y_px, 1),
            "effective_radius_px": round(effective_radius_px, 1),
            "effective_diameter_px": round(2 * effective_radius_px, 1),
            "area_px2": round(math.pi * radius_x_px * radius_y_px, 1),
            "min_effective_radius_px": round(MIN_LANDING_RADIUS_NORM[zone_kind] * min(field.image_w, field.image_h), 1),
            "zone_kind": zone_kind,
        }
        meets_clearance = effective_radius_px >= clearance["min_effective_radius_px"]
    else:
        clearance = {"radius_x_px": None, "radius_y_px": None, "effective_radius_px": None,
                     "effective_diameter_px": None, "area_px2": None, "min_effective_radius_px": None,
                     "zone_kind": zone_kind,
                     "note": "Image dimensions unknown; clearance assessed in normalized units only."}
        meets_clearance = radius >= MIN_LANDING_RADIUS_NORM[zone_kind]
    if radius <= 0:
        reasons.append("Landing zone radius is zero.")
    if not meets_clearance:
        reasons.append(
            f"Clearance too small for {zone_kind}: effective radius "
            f"{clearance['effective_radius_px']} px < required {clearance['min_effective_radius_px']} px.")

    if use_mask:
        zone_px = field.rasterize_circle(center, radius)
        hazard_px = field.mask_pixels(field.hazard_mask)
        inter = len(zone_px & hazard_px)
        hazard_ratio = round(inter / len(zone_px), 6) if zone_px else 1.0
        hazard_iou = round(inter / len(zone_px | hazard_px), 6) if zone_px | hazard_px else 0.0
        safe_px = field.mask_pixels(field.safe_mask)
        safe_ratio = round(len(zone_px & safe_px) / len(zone_px), 6) if zone_px else 0.0
        per_hazard = [{"concept": det["concept"], "box_iou": box_iou(zone_box, det["box"])}
                      for det in field.hazards if box_intersection_area(zone_box, det["box"]) > 0]
    else:
        zone_area = box_area(zone_box)
        hazard_ratio = round(rect_union_area(field.hazard_boxes, clip=zone_box) / zone_area, 6) if zone_area > 0 else 1.0
        hazard_iou = max((box_iou(zone_box, b) for b in field.hazard_boxes), default=0.0)
        safe_ratio = round(rect_union_area(field.safe_boxes, clip=zone_box) / zone_area, 6) if zone_area > 0 else 0.0
        per_hazard = [{"concept": det["concept"],
                       "box_intersection_ratio": round(box_intersection_area(zone_box, det["box"]) / zone_area, 6) if zone_area else 0.0,
                       "box_iou": box_iou(zone_box, det["box"])}
                      for det in field.hazards if box_intersection_area(zone_box, det["box"]) > 0]

    if hazard_ratio > max_hazard_intersection:
        reasons.append(f"Landing zone hazard overlap {hazard_ratio:.1%} exceeds {max_hazard_intersection:.0%} threshold.")
    if field.safe_boxes:
        if safe_ratio < min_safe_surface_overlap:
            reasons.append(
                f"Only {safe_ratio:.1%} of zone overlaps segmented safe surface "
                f"(< {min_safe_surface_overlap:.0%} required).")
    else:
        reasons.append("No safe surface (road/clear ground/rooftop) was segmented under this zone.")

    verified = not reasons
    return {
        "candidate_id": candidate["id"], "kind": "landing_zone",
        "candidate": {k: v for k, v in candidate.items() if k != "center"},
        "status": "verified" if verified else "rejected",
        "color": VERIFIED_COLOR if verified else REJECTED_COLOR,
        "method": "mask" if use_mask else "bbox",
        "hazard_intersection_ratio": hazard_ratio, "hazard_threshold": max_hazard_intersection,
        "hazard_iou": hazard_iou,
        "safe_surface_overlap_ratio": safe_ratio, "min_safe_surface_overlap": min_safe_surface_overlap,
        "zone_bbox_norm": list(zone_box), "clearance": clearance, "meets_clearance": meets_clearance,
        "intersecting_hazards": per_hazard,
        "reasons": reasons or ["Hazard overlap within threshold, on segmented safe surface, clearance sufficient."],
        "requires_reroute": not verified,
    }

def verify_candidates(
    scan_result: dict[str, Any],
    triage_result: dict[str, Any] | None = None,
    corridors: list[dict[str, Any]] | None = None,
    landing_zones: list[dict[str, Any]] | None = None,
    *,
    max_hazard_intersection: float = DEFAULT_MAX_HAZARD_INTERSECTION,
    min_safe_support: float = DEFAULT_MIN_SAFE_SUPPORT,
    min_safe_surface_overlap: float = DEFAULT_MIN_SAFE_SURFACE_OVERLAP,
    require_safe_support: bool = True,
    corridor_buffer_norm: float = DEFAULT_CORRIDOR_BUFFER_NORM,
    default_landing_zone_kind: str = "drone",
) -> dict[str, Any]:
    """Deterministic verification of all candidates. NO model calls."""
    if not isinstance(scan_result, dict) or not scan_result:
        raise ValueError("A Day 2 scan_result is required to verify candidates.")
    detections, image_w, image_h = extract_scan_detections(scan_result)
    if not detections:
        raise ValueError("Scan contains no usable detections (boxes) to verify against.")
    field = DetectionField(detections, image_w, image_h)
    cand_corridors, cand_zones = extract_candidates(triage_result, corridors, landing_zones)

    corridor_results = [verify_corridor(
        c, field, max_hazard_intersection=max_hazard_intersection,
        min_safe_support=min_safe_support, require_safe_support=require_safe_support,
        corridor_buffer_norm=corridor_buffer_norm) for c in cand_corridors]
    zone_results = [verify_landing_zone(
        z, field, max_hazard_intersection=max_hazard_intersection,
        min_safe_surface_overlap=min_safe_surface_overlap,
        default_zone_kind=default_landing_zone_kind) for z in cand_zones]
    all_results = corridor_results + zone_results
    verified = [r for r in all_results if r["status"] == "verified"]
    rejected = [r for r in all_results if r["status"] == "rejected"]
    if not all_results:
        status = "no_candidates"
    elif not rejected:
        status = "verified"
    elif not verified:
        status = "rejected"
    else:
        status = "partially_verified"

    trace: list[dict[str, Any]] = [{
        "step": "verifier", "event": "scan_field_loaded",
        "detail": (f"{len(field.hazards)} hazard / {len(field.safe)} safe detection(s); method={field.method} "
                   f"(masks decoded {field.mask_decoded}/{field.mask_total}"
                   + (f"; mask fallback: {field.mask_errors[0]}" if field.mask_errors else "") + "). "
                   "Geometry: deterministic local Python, zero model calls."),
        "state": "info",
    }]
    for result in all_results:
        trace.append({
            "step": "verifier", "event": f"{result['kind']}_{result['status']}",
            "candidate_id": result["candidate_id"], "kind": result["kind"],
            "hazard_intersection_ratio": result["hazard_intersection_ratio"],
            "detail": (f"{result['candidate_id']}: {result['status'].upper()} - hazard intersection "
                       f"{result['hazard_intersection_ratio']:.1%} (threshold {max_hazard_intersection:.0%}) "
                       f"via {result['method']}. " + " ".join(result["reasons"])),
            "state": "verified" if result["status"] == "verified" else "rejected",
        })

    corridor_by_id = {c["id"]: c for c in cand_corridors}
    return {
        "status": status, "engine": "deterministic_python", "model_calls_in_geometry": 0,
        "method": field.method,
        "image": {"width": image_w or None, "height": image_h or None},
        "thresholds": {
            "max_hazard_intersection_ratio": max_hazard_intersection,
            "min_safe_support_ratio": min_safe_support if require_safe_support else None,
            "min_safe_surface_overlap_ratio": min_safe_surface_overlap,
            "corridor_buffer_norm": corridor_buffer_norm,
            "min_landing_radius_norm": MIN_LANDING_RADIUS_NORM,
        },
        "field": {
            "hazard_detections": len(field.hazards), "safe_detections": len(field.safe),
            "hazard_concepts": sorted({d["concept"] for d in field.hazards}),
            "safe_concepts": sorted({d["concept"] for d in field.safe}),
            "masks_decoded": field.mask_decoded, "masks_present": field.mask_total,
            "mask_fallback_reason": field.mask_errors[0] if field.mask_errors else None,
        },
        "candidates": {
            "corridors": [{k: v for k, v in c.items() if k != "points"} for c in cand_corridors],
            "landing_zones": [{k: v for k, v in z.items() if k != "center"} for z in cand_zones],
        },
        "corridor_results": corridor_results, "landing_zone_results": zone_results,
        "verified_candidates": {
            "corridors": [{**r["candidate"], "verification": {"hazard_intersection_ratio": r["hazard_intersection_ratio"], "safe_support_ratio": r["safe_support_ratio"], "method": r["method"]}}
                          for r in corridor_results if r["status"] == "verified"],
            "landing_zones": [{**r["candidate"], "verification": {"hazard_intersection_ratio": r["hazard_intersection_ratio"], "hazard_iou": r["hazard_iou"], "clearance": r["clearance"], "method": r["method"]}}
                              for r in zone_results if r["status"] == "verified"],
        },
        "rejected_candidates": {
            "corridors": [r for r in corridor_results if r["status"] == "rejected"],
            "landing_zones": [r for r in zone_results if r["status"] == "rejected"],
        },
        "summary": {"total": len(all_results), "verified": len(verified), "rejected": len(rejected),
                    "corridors_verified": sum(1 for r in corridor_results if r["status"] == "verified"),
                    "landing_zones_verified": sum(1 for r in zone_results if r["status"] == "verified")},
        "trace": trace,
    }


# --------------------------------------------------------------------------- #
# OpenStreetMap Overpass - nearby emergency facilities (free, AGENTS.md SS2)
# --------------------------------------------------------------------------- #
FACILITY_AMENITIES = ("hospital", "clinic", "doctors", "fire_station", "police")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * r * math.asin(min(1.0, math.sqrt(a))), 1)


def build_overpass_query(latitude: float, longitude: float, radius_m: int) -> str:
    clauses = "".join(
        f'node["amenity"="{a}"](around:{radius_m},{latitude},{longitude});'
        f'way["amenity"="{a}"](around:{radius_m},{latitude},{longitude});'
        for a in FACILITY_AMENITIES)
    return f"[out:json][timeout:25];({clauses});out center tags;"


def parse_overpass_response(payload: dict[str, Any], latitude: float, longitude: float) -> list[dict[str, Any]]:
    facilities: list[dict[str, Any]] = []
    for el in payload.get("elements") or []:
        center = el.get("center") or {}
        lat = el.get("lat") if el.get("lat") is not None else center.get("lat")
        lon = el.get("lon") if el.get("lon") is not None else center.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags") or {}
        address = tags.get("addr:full") or " ".join(
            v for v in [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:city")] if v) or None
        facilities.append({
            "name": tags.get("name") or tags.get("operator") or "Unnamed facility",
            "type": tags.get("amenity") or "unknown",
            "latitude": float(lat), "longitude": float(lon),
            "distance_m": haversine_m(latitude, longitude, float(lat), float(lon)),
            "osm_type": el.get("type"), "osm_id": el.get("id"),
            "address": address, "emergency": tags.get("emergency"),
        })
    facilities.sort(key=lambda f: f["distance_m"])
    return facilities


async def query_emergency_facilities(
    latitude: float | None, longitude: float | None, *,
    radius_m: int = 5000, http_client: httpx.AsyncClient | None = None,
    endpoint: str = OVERPASS_ENDPOINT, timeout: float = 30.0, max_retries: int = 1,
) -> dict[str, Any]:
    """Nearby hospitals/clinics/fire/police via Overpass. Context only."""
    if latitude is None or longitude is None:
        return {"status": "not_queried", "provider": "OpenStreetMap Overpass API",
                "reason": "No geographic coordinates supplied. Image-normalized candidate coordinates are not GPS and are never converted to fake lat/lon.",
                "facilities": [], "counts_by_type": {}}
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("latitude/longitude out of range.")
    radius_m = int(min(50000, max(100, radius_m)))
    query = build_overpass_query(latitude, longitude, radius_m)
    started = time.perf_counter()
    headers = {"User-Agent": "CrisisGrid/0.4 (Meta Hackathon; deterministic verifier)"}
    facilities: list[dict[str, Any]] | None = None
    latency_ms = 0.0
    last_error: dict[str, Any] | None = None
    # Overpass is a free shared service and answers 502 "at capacity" under
    # load (live-observed Oct 30): retry once with backoff, then degrade to
    # an honest error state - facilities never block geometry.
    for attempt in range(int(max(0, max_retries)) + 1):
        try:
            if http_client is not None:
                response = await http_client.post(endpoint, data={"data": query}, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(endpoint, data={"data": query}, headers=headers)
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            if response.status_code >= 400:
                last_error = {"status": "error", "provider": "OpenStreetMap Overpass API",
                              "http_status": response.status_code, "facilities": [], "counts_by_type": {},
                              "latency_ms": latency_ms, "attempts": attempt + 1,
                              "message": f"Overpass returned HTTP {response.status_code}; verification geometry is unaffected."}
                if response.status_code in (429, 502, 503, 504) and attempt < max_retries:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                return last_error
            facilities = parse_overpass_response(response.json(), latitude, longitude)
            break
        except Exception as exc:
            last_error = {"status": "error", "provider": "OpenStreetMap Overpass API",
                          "facilities": [], "counts_by_type": {}, "attempts": attempt + 1,
                          "message": f"Overpass query failed ({type(exc).__name__}: {exc}); verification geometry is unaffected."}
            if attempt < max_retries:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            return last_error
    if facilities is None:
        return last_error or {"status": "error", "provider": "OpenStreetMap Overpass API",
                              "facilities": [], "counts_by_type": {}, "message": "Overpass unavailable."}
    counts: dict[str, int] = {}
    for fac in facilities:
        counts[fac["type"]] = counts.get(fac["type"], 0) + 1
    return {"status": "ok", "provider": "OpenStreetMap Overpass API", "endpoint": endpoint,
            "query": {"latitude": latitude, "longitude": longitude, "radius_m": radius_m},
            "facilities": facilities, "counts_by_type": counts, "latency_ms": latency_ms,
            "note": "Facilities are geographic context for commanders; they do not alter deterministic image-space verification."}

# --------------------------------------------------------------------------- #
# muse-spark-1.3 self-correction loop (model proposes, Python disposes)
# --------------------------------------------------------------------------- #
_CORRECTION_DEVELOPER = """You are CrisisGrid's multimodal triage reasoner (muse-spark-1.3) in a VERIFIER-FORCED RE-ROUTE.
A deterministic Python verifier REJECTED some candidate evacuation corridors / landing zones because they intersect sam-3.1 hazard geometry or lack safe-surface support/clearance.
Revise ONLY the rejected candidates. Keep their ids. Move corridor points and landing-zone centres away from the intersecting hazards and onto the listed safe infrastructure (road, bridge, clear flat ground, rooftop), using the provided hazard/safe boxes (normalized coords, origin top-left).
Return ONLY one JSON object, no markdown:
{"candidate_evacuation_corridors": [{"id": "same-id", "name": "string", "purpose": "evacuation", "points_norm": [[0.0,0.0],[1.0,1.0]], "start_label": "string", "end_label": "string", "rationale": "what changed and why it avoids the hazard", "grounded_concepts": ["road"]}], "candidate_landing_zones": [{"id": "same-id", "name": "string", "center_norm": [0.5,0.5], "radius_norm": 0.05, "surface_concept": "clear flat ground", "rationale": "what changed", "grounded_concepts": ["clear flat ground"]}], "changes_summary": "string"}
Include an entry for every rejected candidate id. Do not claim anything is verified or safe - the verifier will re-check you."""


def build_correction_prompt(rejected_results: list[dict[str, Any]], scan_summary: dict[str, Any],
                            facilities: dict[str, Any] | None = None) -> str:
    evidence = [{"candidate_id": r["candidate_id"], "kind": r["kind"],
                 "hazard_intersection_ratio": r["hazard_intersection_ratio"],
                 "intersecting_hazards": r["intersecting_hazards"], "reasons": r["reasons"],
                 "rejected_candidate": r["candidate"]} for r in rejected_results]
    facility_note = ""
    if facilities and facilities.get("status") == "ok" and facilities.get("facilities"):
        facility_note = "\nNEARBY EMERGENCY FACILITIES (geographic context only): " + "; ".join(
            f"{f['name']} ({f['type']}, {f['distance_m']} m)" for f in facilities["facilities"][:3])
    return ("REJECTED CANDIDATES WITH DETERMINISTIC VERIFIER EVIDENCE:\n"
            f"{json.dumps(evidence, indent=2)}\n\n"
            "SAM-3.1 SCAN SUMMARY (safe/hazard boxes to route around/onto):\n"
            f"{json.dumps(scan_summary, indent=2)}{facility_note}\n\n"
            "Propose corrected candidates now. Return ONLY the JSON object.")


async def request_reroute(
    rejected_results: list[dict[str, Any]], scan_result: dict[str, Any], *,
    facilities: dict[str, Any] | None = None, client: Any = None,
    client_factory: Callable[[], Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """One muse-spark-1.3 re-route call. Returns (corridors, zones, latency_ms)."""
    active_client = client or (client_factory or get_async_meta_client)()
    close_when_done = client is None and client_factory is None
    started = time.perf_counter()
    try:
        response = await active_client.responses.create(
            model=CORRECTION_MODEL,
            input=[
                {"type": "message", "role": "developer",
                 "content": [{"type": "input_text", "text": _CORRECTION_DEVELOPER}]},
                {"type": "message", "role": "user",
                 "content": [{"type": "input_text", "text": build_correction_prompt(
                     rejected_results, summarize_scan(scan_result), facilities)}]},
            ],
        )
    finally:
        if close_when_done:
            close = getattr(active_client, "close", None)
            if callable(close):
                result = close()
                if hasattr(result, "__await__"):
                    await result
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    proposal = parse_spark_triage(extract_output_text(response))  # Day 3 candidate schema
    normalized = normalize_assessment(proposal)
    return (normalized["candidate_evacuation_corridors"],
            normalized["candidate_landing_zones"], latency_ms)


def _merge_corrections(current_corridors, current_zones, rejected_ids, new_corridors, new_zones):
    """Replace rejected candidates with Spark revisions (ids forced stable)."""
    replaced: list[str] = []

    def merge(current, revised):
        by_id = {str(c.get("id")): c for c in revised}
        pool = [c for c in revised if str(c.get("id")) not in rejected_ids]
        out = []
        for cand in current:
            cid = str(cand.get("id"))
            if cid not in rejected_ids:
                out.append(cand)
                continue
            replacement = by_id.get(cid)
            if replacement is None and pool:
                replacement = dict(pool.pop(0))
            if replacement is None:
                out.append(cand)  # Spark omitted it: stays rejected, never deleted
                continue
            replaced.append(cid)
            out.append({**replacement, "id": cid})
        return out

    return merge(current_corridors, new_corridors), merge(current_zones, new_zones), replaced


async def run_verification_loop(
    scan_result: dict[str, Any], triage_result: dict[str, Any] | None = None,
    corridors: list[dict[str, Any]] | None = None,
    landing_zones: list[dict[str, Any]] | None = None, *,
    latitude: float | None = None, longitude: float | None = None,
    facility_radius_m: int = 5000, auto_correct: bool = True,
    max_correction_attempts: int = 2, spark_client: Any = None,
    spark_client_factory: Callable[[], Any] | None = None,
    osm_http_client: httpx.AsyncClient | None = None,
    overpass_endpoint: str = OVERPASS_ENDPOINT, **verify_options: Any,
) -> dict[str, Any]:
    """Day 4 pipeline: deterministic verify -> Spark re-route -> re-verify."""
    started = time.perf_counter()
    trace: list[dict[str, Any]] = []
    facilities = await query_emergency_facilities(
        latitude, longitude, radius_m=facility_radius_m,
        http_client=osm_http_client, endpoint=overpass_endpoint)
    if facilities["status"] == "ok":
        trace.append({"step": "osm-overpass", "event": "facilities_loaded",
                      "detail": f"{len(facilities['facilities'])} emergency facilit(ies) within {facility_radius_m} m ({facilities['counts_by_type']}). Context only - geometry unchanged.",
                      "state": "info"})
    elif facilities["status"] == "error":
        trace.append({"step": "osm-overpass", "event": "facilities_unavailable",
                      "detail": facilities.get("message", "Overpass unavailable."), "state": "caution"})
    else:
        trace.append({"step": "osm-overpass", "event": "facilities_not_queried",
                      "detail": facilities["reason"], "state": "info"})

    cand_corridors, cand_zones = extract_candidates(triage_result, corridors, landing_zones)
    current_corridors = [{k: v for k, v in c.items() if k != "points"} for c in cand_corridors]
    current_zones = [{k: v for k, v in z.items() if k != "center"} for z in cand_zones]

    verification = verify_candidates(scan_result, corridors=current_corridors,
                                     landing_zones=current_zones, **verify_options)
    trace.extend(verification["trace"])
    initial_verification = verification
    history: list[dict[str, Any]] = []
    attempts_used = 0
    correction_status = "not_needed" if verification["status"] == "verified" else "not_attempted"
    max_correction_attempts = int(min(3, max(0, max_correction_attempts)))

    while verification["summary"]["rejected"] > 0 and auto_correct and attempts_used < max_correction_attempts:
        rejected_results = (verification["rejected_candidates"]["corridors"]
                            + verification["rejected_candidates"]["landing_zones"])
        rejected_ids = {r["candidate_id"] for r in rejected_results}
        attempts_used += 1
        trace.append({"step": "verifier", "event": "reroute_forced",
                      "detail": f"{len(rejected_ids)} candidate(s) rejected: {sorted(rejected_ids)}. Forcing muse-spark-1.3 re-route (attempt {attempts_used}).",
                      "state": "rejected"})
        try:
            new_corridors, new_zones, spark_ms = await request_reroute(
                rejected_results, scan_result, facilities=facilities,
                client=spark_client, client_factory=spark_client_factory)
        except Exception as exc:
            correction_status = "correction_failed"
            trace.append({"step": "muse-spark-1.3", "event": "reroute_failed",
                          "detail": f"Re-route attempt {attempts_used} failed ({type(exc).__name__}: {exc}). Candidates remain rejected; none were silently altered.",
                          "state": "rejected"})
            history.append({"attempt": attempts_used, "rejected_candidate_ids": sorted(rejected_ids),
                            "status": "failed", "error": f"{type(exc).__name__}: {exc}"})
            break
        current_corridors, current_zones, replaced_ids = _merge_corrections(
            current_corridors, current_zones, rejected_ids, new_corridors, new_zones)
        trace.append({"step": "muse-spark-1.3", "event": "reroute_proposed",
                      "detail": f"Re-route attempt {attempts_used} in {spark_ms} ms replaced {replaced_ids or 'no'} candidate(s); deterministic verifier re-checking.",
                      "state": "caution", "latency_ms": spark_ms})
        verification = verify_candidates(scan_result, corridors=current_corridors,
                                         landing_zones=current_zones, **verify_options)
        trace.extend(verification["trace"])
        history.append({"attempt": attempts_used, "rejected_candidate_ids": sorted(rejected_ids),
                        "replaced_candidate_ids": replaced_ids, "spark_latency_ms": spark_ms,
                        "result_status": verification["status"],
                        "verified_after": verification["summary"]["verified"],
                        "rejected_after": verification["summary"]["rejected"]})
        correction_status = "corrected" if verification["summary"]["rejected"] == 0 else "exhausted"

    if verification["summary"]["rejected"] > 0:
        if not auto_correct:
            correction_status = "disabled"
            trace.append({"step": "verifier", "event": "reroute_skipped",
                          "detail": "Auto-correction disabled for this request; rejected candidates stand.",
                          "state": "rejected"})
        elif attempts_used >= max_correction_attempts and correction_status not in ("correction_failed",):
            correction_status = "exhausted"
            trace.append({"step": "verifier", "event": "reroute_exhausted",
                          "detail": f"Self-correction budget ({max_correction_attempts}) exhausted; remaining candidates stay REJECTED and must not be dispatched.",
                          "state": "rejected"})

    final_status = verification["status"]
    return {
        "status": final_status, "day": 4, "engine": "deterministic_python",
        "model_calls_in_geometry": 0,
        "correction_model": CORRECTION_MODEL if attempts_used else None,
        "initial_verification": initial_verification, "final_verification": verification,
        "verified_candidates": verification["verified_candidates"],
        "rejected_candidates": verification["rejected_candidates"],
        "correction": {"enabled": auto_correct, "max_attempts": max_correction_attempts,
                       "attempts_used": attempts_used, "status": correction_status, "history": history},
        "emergency_facilities": facilities, "trace": trace,
        "total_latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "verification_status": ("verified_by_deterministic_python" if final_status == "verified"
                                else "no_candidates_to_verify" if final_status == "no_candidates"
                                else "not_verified_rejected_or_partial"),
        "dispatch_ready": final_status == "verified",
        "next_step": ("Only verified_candidates may flow into muse-wonder-1.0 dispatch."
                      if final_status == "verified" else
                      "Do NOT dispatch rejected/unverified candidates. Re-plan or wait for a new scan."),
    }


# Friendly aliases
verify_proposals = verify_candidates
run_verifiable_loop = run_verification_loop
