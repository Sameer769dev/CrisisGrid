"""Parallel sam-3.1 hazard & safe-zone scanner - Day 2 (Oct 28, 2026).

Meta Model API contract (AGENTS.md SS3.1, binding):
- Endpoint: POST https://api.meta.ai/v1/responses via client.responses.create
- Model: sam-3.1
- CRITICAL: ONE short concrete noun phrase per request. This module therefore
  fans out one async request per concept with asyncio.gather - it never joins
  concepts into a single prompt.
- Output is parsed ONLY by the deterministic regex parser in sam_parser.py.

Colour law (AGENTS.md SS6): hazard = red, safe/passable = green,
custom/unclassified concept = yellow (unverified).
"""
from __future__ import annotations

import asyncio
import base64
import io
import time
from typing import Any, Awaitable, Callable, Iterable

try:  # repo-root imports (uvicorn backend.main:app)
    from backend.config import get_async_meta_client as _config_async_client
    from backend.services.sam_parser import SamDetection, parse_sam_output
except ImportError:  # backend/ imports (uvicorn main:app, tests)
    from config import get_async_meta_client as _config_async_client
    from services.sam_parser import SamDetection, parse_sam_output

SAM_MODEL = "sam-3.1"

# Canonical concept sets. `fire` is part of the AGENTS.md/ROADMAP canonical
# hazard set alongside the hazards named in the Day 2 tasking.
HAZARD_CONCEPTS: tuple[str, ...] = (
    "flood water",
    "debris",
    "fire",
    "damaged building",
    "stranded vehicle",
)
SAFE_ZONE_CONCEPTS: tuple[str, ...] = (
    "road",
    "bridge",
    "clear flat ground",
    "rooftop",
)
PASSABLE_CONCEPTS = SAFE_ZONE_CONCEPTS  # ROADMAP wording alias

CONCEPT_KIND: dict[str, str] = {
    **{c: "hazard" for c in HAZARD_CONCEPTS},
    **{c: "safe_zone" for c in SAFE_ZONE_CONCEPTS},
}
CONCEPT_COLORS: dict[str, str] = {"hazard": "#FF2D20", "safe_zone": "#00C853", "custom": "#FFD600"}
DEFAULT_CONCEPTS: tuple[str, ...] = HAZARD_CONCEPTS + SAFE_ZONE_CONCEPTS

_SUPPORTED_MIME = {"image/jpeg", "image/png", "image/webp"}
_MAX_CONCEPT_CHARS = 80


# --------------------------------------------------------------------------- #
# Helpers (pure / deterministic - unit-testable without any model call)
# --------------------------------------------------------------------------- #
def concept_kind(concept: str) -> str:
    return CONCEPT_KIND.get(concept.strip().lower(), "custom")


def validate_concepts(concepts: Iterable[str] | None) -> list[str]:
    """Validate + de-duplicate concepts. Each entry must be ONE noun phrase."""
    if concepts is None:
        return list(DEFAULT_CONCEPTS)
    cleaned: list[str] = []
    for raw in concepts:
        concept = " ".join(str(raw).strip().lower().split())
        if not concept:
            continue
        if len(concept) > _MAX_CONCEPT_CHARS or any(c in concept for c in ",;\n\r"):
            raise ValueError(
                f"Invalid sam-3.1 concept {raw!r}: each concept must be a single short "
                "concrete noun phrase (one phrase per request, no separators)."
            )
        if concept not in cleaned:
            cleaned.append(concept)
    if not cleaned:
        raise ValueError("At least one sam-3.1 concept is required.")
    return cleaned


def sniff_media_type(image_bytes: bytes, declared: str | None = None) -> str:
    """Best-effort image media type from magic bytes, falling back to declared."""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    media = (declared or "").split(";")[0].strip().lower()
    if media == "image/jpg":
        media = "image/jpeg"
    return media if media in _SUPPORTED_MIME else "image/jpeg"


def probe_image(image_bytes: bytes) -> tuple[int | None, int | None]:
    """Return actual (width, height) via Pillow when available; (None, None) if not."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as img:
            img.verify()
        with Image.open(io.BytesIO(image_bytes)) as img:
            return int(img.width), int(img.height)
    except Exception:
        return None, None


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def normalize_detection(detection: SamDetection, concept: str) -> dict[str, Any] | None:
    """Convert one parsed SAM detection to pixel + normalized (0-1) geometry.

    Normalization uses the image space SAM itself declares (w/h in the wire
    format), per AGENTS.md SS3.1. Returns None for a degenerate declared size.
    """
    if detection.w <= 0 or detection.h <= 0:
        return None
    kind = concept_kind(concept)
    x_lo, x_hi = sorted((detection.x1, detection.x2))
    y_lo, y_hi = sorted((detection.y1, detection.y2))
    x_min, x_max = _clamp01(x_lo / detection.w), _clamp01(x_hi / detection.w)
    y_min, y_max = _clamp01(y_lo / detection.h), _clamp01(y_hi / detection.h)
    mask = None
    if detection.mask_data is not None:
        mask = {
            "x": detection.mask_x,
            "y": detection.mask_y,
            "width": detection.w,
            "height": detection.h,
            "format": "sam-3.1-rle",
            "data": detection.mask_data,
        }
    return {
        "concept": concept,
        "kind": kind,
        "color": CONCEPT_COLORS[kind],
        # Pixel-space box in SAM's declared image coordinates.
        "bbox_px": {"x1": x_lo, "y1": y_lo, "x2": x_hi, "y2": y_hi},
        # Normalized 0-1 box for resolution-independent canvas rendering (Day 6).
        "bbox": {
            "x_min": round(x_min, 6),
            "y_min": round(y_min, 6),
            "x_max": round(x_max, 6),
            "y_max": round(y_max, 6),
            "width": round(x_max - x_min, 6),
            "height": round(y_max - y_min, 6),
        },
        # [x_min, y_min, x_max, y_max] convenience form for canvas code.
        "bbox_xyxy_norm": [round(x_min, 6), round(y_min, 6), round(x_max, 6), round(y_max, 6)],
        "area_fraction": round(max(0.0, (x_max - x_min) * (y_max - y_min)), 6),
        "mask": mask,
        "has_mask": mask is not None,
    }


def extract_output_text(response: Any) -> str:
    """Extract output_text from a Responses API result (object or dict shape)."""
    if response is None:
        return ""
    if isinstance(response, dict):
        if response.get("output_text"):
            return str(response["output_text"])
        chunks: list[str] = []
        for item in response.get("output") or []:
            for part in (item or {}).get("content") or []:
                if isinstance(part, dict) and part.get("text"):
                    chunks.append(str(part["text"]))
        return "".join(chunks)
    text = getattr(response, "output_text", None)
    if text:
        return str(text)
    chunks = []
    for item in getattr(response, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                chunks.append(str(part_text))
    return "".join(chunks)


def get_async_meta_client():
    """Async OpenAI SDK client pointed ONLY at the official Meta Model API."""
    return _config_async_client()


# --------------------------------------------------------------------------- #
# Core scanner
# --------------------------------------------------------------------------- #
async def scan_one_concept(
    client: Any,
    concept: str,
    image_data_url: str,
) -> dict[str, Any]:
    """Run exactly ONE sam-3.1 request for exactly ONE noun phrase."""
    kind = concept_kind(concept)
    started = time.perf_counter()
    base: dict[str, Any] = {
        "concept": concept,
        "kind": kind,
        "color": CONCEPT_COLORS[kind],
        "model": SAM_MODEL,
    }
    try:
        response = await client.responses.create(
            model=SAM_MODEL,
            input=[{
                "type": "message",
                "role": "user",
                "content": [
                    # ONE short concrete noun phrase - never a joined list.
                    {"type": "input_text", "text": concept},
                    {"type": "input_image", "image_url": image_data_url},
                ],
            }],
        )
        parsed = parse_sam_output(extract_output_text(response))
        detections = [
            normalized
            for det in parsed.detections
            if (normalized := normalize_detection(det, concept)) is not None
        ]
        return {
            **base,
            "status": "ok",
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "detection_count": len(detections),
            "mask_count": sum(1 for d in detections if d["has_mask"]),
            "sam_image_size": (
                {"width": parsed.image_size[0], "height": parsed.image_size[1]}
                if parsed.image_size else None
            ),
            "detections": detections,
            "error": None,
        }
    except Exception as exc:  # one failed concept must not sink the whole scan
        return {
            **base,
            "status": "error",
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "detection_count": 0,
            "mask_count": 0,
            "sam_image_size": None,
            "detections": [],
            "error": {"type": type(exc).__name__, "message": str(exc)[:500]},
        }


async def scan_hazards(
    image_bytes: bytes,
    *,
    media_type: str | None = None,
    filename: str | None = None,
    concepts: Iterable[str] | None = None,
    client: Any = None,
    client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Scan one image for all hazard + safe-zone concepts, in parallel.

    Returns a JSON-serializable payload ready for the Day 6 canvas:
    per-concept normalized boxes/masks, summary counts, and an agent trace
    with per-concept latency and box/mask counts (ROADMAP Day 2 acceptance).
    """
    if not image_bytes:
        raise ValueError("Empty image: upload a JPEG, PNG, or WebP disaster image.")
    concept_list = validate_concepts(concepts)
    resolved_media = sniff_media_type(image_bytes, media_type)
    actual_w, actual_h = probe_image(image_bytes)
    if actual_w is None:
        raise ValueError("Could not decode the uploaded file as an image (JPEG/PNG/WebP expected).")

    image_data_url = f"data:{resolved_media};base64,{base64.b64encode(image_bytes).decode()}"
    active_client = client or (client_factory or get_async_meta_client)()
    close_when_done = client is None and client_factory is None

    started = time.perf_counter()
    try:
        # Parallel fan-out: one in-flight sam-3.1 request per concept.
        layers: list[dict[str, Any]] = await asyncio.gather(
            *(scan_one_concept(active_client, concept, image_data_url) for concept in concept_list)
        )
    finally:
        if close_when_done:
            close = getattr(active_client, "close", None)
            if callable(close):
                result = close()
                if isinstance(result, Awaitable):
                    await result
    total_ms = round((time.perf_counter() - started) * 1000, 1)

    flat_detections = [d for layer in layers for d in layer["detections"]]
    ok_count = sum(1 for layer in layers if layer["status"] == "ok")
    status = "ok" if ok_count == len(layers) else ("partial" if ok_count else "failed")

    def _kind_totals(kind: str) -> dict[str, Any]:
        kind_layers = [layer for layer in layers if layer["kind"] == kind]
        return {
            "concepts_with_detections": [l["concept"] for l in kind_layers if l["detection_count"]],
            "detections": sum(l["detection_count"] for l in kind_layers),
            "masks": sum(l["mask_count"] for l in kind_layers),
            # Sum of box area fractions; overlapping boxes may double-count.
            "box_area_fraction_sum": round(
                sum(d["area_fraction"] for d in flat_detections if d["kind"] == kind), 6
            ),
        }

    trace: list[dict[str, Any]] = [{
        "step": "sam-3.1",
        "event": "scan_started",
        "detail": (
            f"{len(concept_list)} concepts fanned out in parallel "
            f"(one noun phrase per request) on {actual_w}x{actual_h} image."
        ),
        "state": "info",
    }]
    trace += [{
        "step": "sam-3.1",
        "event": "concept_complete",
        "concept": layer["concept"],
        "kind": layer["kind"],
        "status": layer["status"],
        "latency_ms": layer["latency_ms"],
        "detections": layer["detection_count"],
        "masks": layer["mask_count"],
        "detail": (
            f"{layer['concept']}: {layer['detection_count']} box(es), "
            f"{layer['mask_count']} mask(s) in {layer['latency_ms']} ms."
            if layer["status"] == "ok"
            else f"{layer['concept']}: request failed - {(layer['error'] or {}).get('message', 'unknown error')}"
        ),
        "state": "info" if layer["status"] == "ok" else "rejected",
    } for layer in layers]
    trace.append({
        "step": "sam-3.1",
        "event": "scan_complete",
        "detail": (
            f"{len(flat_detections)} total detection(s) across {ok_count}/{len(layers)} "
            f"successful concept layer(s) in {total_ms} ms. "
            "Segmentation only - corridors are NOT verified safe until the deterministic geometry verifier runs."
        ),
        "state": "info",
    })

    return {
        "status": status,
        "model": SAM_MODEL,
        "image": {
            "filename": filename,
            "media_type": resolved_media,
            "width": actual_w,
            "height": actual_h,
            "size_bytes": len(image_bytes),
        },
        "concepts_requested": concept_list,
        "concept_layers": layers,
        "detections": flat_detections,
        "summary": {
            "total_detections": len(flat_detections),
            "total_masks": sum(1 for d in flat_detections if d["has_mask"]),
            "concepts_succeeded": ok_count,
            "concepts_failed": len(layers) - ok_count,
            "total_latency_ms": total_ms,
            "hazards": _kind_totals("hazard"),
            "safe_zones": _kind_totals("safe_zone"),
        },
        "trace": trace,
        # Day 2 segments only. The Day 4 verifier is the only component that
        # may mark a corridor or landing zone as verified/safe.
        "verification_status": "unverified_segmentation_only",
    }


# Friendly aliases
scan_image = scan_hazards
scan_hazard_image = scan_hazards
