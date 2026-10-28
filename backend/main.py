"""CrisisGrid FastAPI backend - Day 8 (Nov 3, 2026).

Live:
  GET  /health                    - liveness + model-key status (never the key)
  GET  /api/config/status         - frontend-safe config status
  POST /api/sam/parse             - deterministic sam-3.1 wire-format parser (offline)
  GET  /api/scan-hazards/concepts - Day 2 concept sets (hazards / safe zones)
  POST /api/scan-hazards          - Day 2 parallel sam-3.1 scan (alias: POST /api/scan)
  POST /api/triage                - Day 3 field radio (WAV) or text fallback + optional
                                    Day 2 scan JSON / image -> muse-spark-1.3 triage
  POST /api/triage/text           - Day 3 JSON text-fallback variant (typed clients)
  POST /api/verify                - Day 4 deterministic verifier (bbox/mask IoU,
                                    clearance) + OSM facilities + muse-spark-1.3
                                    self-correction loop when a candidate is rejected
  GET  /api/verify/readiness      - Day 4 thresholds / trust contract
  POST /api/dispatch              - Day 5 verified-only dispatch: muse-wonder-1.0
                                    (reasoning high) + muse-image-1.0 briefing card
  GET  /api/dispatch/readiness    - Day 5 trust contract (verified input only)
  POST /api/run-crisisgrid        - Day 5 unified pipeline: scan -> triage ->
                                    verify -> dispatch in one call
  POST /api/delta                 - Day 7 deterministic before/after damage delta
                                    (greedy IoU box matching, zero model calls)
  POST /api/delta/verify-clearance - Day 7 post-clearance re-verification: same
                                    candidates re-checked by the Day 4 verifier
                                    against the AFTER scan only
  POST /api/sectors/rank          - Day 7 multi-sector triage ranking
                                    (deterministic score, zero model calls)
  GET  /api/presets               - Day 8 pre-loaded disaster presets (static
                                    honest metadata; results always run live)

Run:  uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

import json

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:  # works as `uvicorn backend.main:app` from repo root
    from backend.config import FRONTEND_ORIGIN, META_API_BASE_URL, model_api_key_configured
    from backend.services.sam_hazard_scanner import (
        CONCEPT_COLORS,
        HAZARD_CONCEPTS,
        SAFE_ZONE_CONCEPTS,
        scan_hazards,
    )
    from backend.services.sam_parser import parse_sam_output
    from backend.services.voice_and_triage import (
        TRANSCRIBE_MODEL,
        TRIAGE_MODEL,
        TranscriptionError,
        TriageParseError,
        run_triage,
    )
    from backend.services.verifiable_corridor_engine import (
        DEFAULT_MAX_HAZARD_INTERSECTION,
        OVERPASS_ENDPOINT,
        run_verification_loop,
    )
    from backend.services.damage_delta import compute_damage_delta, rank_sectors, verify_clearance
    from backend.services.presets import get_preset, list_presets
    from backend.services.wonder_commander import (
        BRIEFING_MODEL,
        DISPATCH_MODEL,
        DispatchParseError,
        NoDispatchableCandidatesError,
        run_crisisgrid_pipeline,
        run_dispatch,
    )
except ImportError:  # works as `uvicorn main:app` from backend/
    from config import FRONTEND_ORIGIN, META_API_BASE_URL, model_api_key_configured
    from services.sam_hazard_scanner import (
        CONCEPT_COLORS,
        HAZARD_CONCEPTS,
        SAFE_ZONE_CONCEPTS,
        scan_hazards,
    )
    from services.sam_parser import parse_sam_output
    from services.voice_and_triage import (
        TRANSCRIBE_MODEL,
        TRIAGE_MODEL,
        TranscriptionError,
        TriageParseError,
        run_triage,
    )
    from services.verifiable_corridor_engine import (
        DEFAULT_MAX_HAZARD_INTERSECTION,
        OVERPASS_ENDPOINT,
        run_verification_loop,
    )
    from services.damage_delta import compute_damage_delta, rank_sectors, verify_clearance
    from services.presets import get_preset, list_presets
    from services.wonder_commander import (
        BRIEFING_MODEL,
        DISPATCH_MODEL,
        DispatchParseError,
        NoDispatchableCandidatesError,
        run_crisisgrid_pipeline,
        run_dispatch,
    )

MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 MB upload ceiling for drone/street imagery
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB field-radio WAV ceiling (Day 3)

app = FastAPI(
    title="CrisisGrid API",
    description="Autonomous Multimodal Disaster Triage & Emergency Dispatch Agent - Meta Model API only.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SamParseRequest(BaseModel):
    output_text: str = Field(..., description="Raw sam-3.1 output_text wire format to parse deterministically.")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "CrisisGrid Engine",
        "version": app.version,
        "meta_api_base_url": META_API_BASE_URL,
        "model_api_key_configured": model_api_key_configured(),
        "models": {
            "segmentation": "sam-3.1",
            "transcription": "muse-voice-transcribe-1.0",
            "triage": "muse-spark-1.3",
            "dispatch": "muse-wonder-1.0",
            "briefing_image": "muse-image-1.0",
        },
    }


@app.get("/api/config/status")
def config_status() -> dict:
    configured = model_api_key_configured()
    return {
        "model_api_key_configured": configured,
        "meta_api_base_url": META_API_BASE_URL,
        "hint": None if configured else "Set MODEL_API_KEY in .env (see .env.example) and restart the backend.",
    }


@app.post("/api/sam/parse")
def sam_parse(payload: SamParseRequest) -> dict:
    """Offline deterministic parser - proves the Day 2 pipeline contract today."""
    return parse_sam_output(payload.output_text).to_dict()


@app.get("/api/scan-hazards/concepts")
def scan_hazard_concepts() -> dict:
    """Day 2 concept vocabulary. sam-3.1 still receives ONE phrase per request."""
    return {
        "model": "sam-3.1",
        "hazards": [{"concept": c, "kind": "hazard", "color": CONCEPT_COLORS["hazard"]} for c in HAZARD_CONCEPTS],
        "safe_zones": [
            {"concept": c, "kind": "safe_zone", "color": CONCEPT_COLORS["safe_zone"]} for c in SAFE_ZONE_CONCEPTS
        ],
        "note": "Segmentation only - nothing here is a verified safe corridor until the deterministic geometry verifier runs.",
    }


@app.post("/api/scan-hazards")
@app.post("/api/scan")  # ROADMAP Day 2 alias
async def scan_hazards_endpoint(
    file: UploadFile = File(..., description="Disaster image (JPEG/PNG/WebP): aerial, drone, or street level."),
    concepts: str | None = Form(
        default=None,
        description="Optional comma-separated override of sam-3.1 concepts. Each entry is still sent as ONE separate request.",
    ),
) -> dict:
    """Day 2: parallel sam-3.1 segmentation into hazards vs. safe zones.

    Returns normalized (0-1) + pixel boxes and RLE mask payloads per concept,
    per-concept latency/counts, and an agent trace. Boxes/masks are proposals
    from the model - NOT verified safe routes (that is Day 4's job).
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail={"status": "empty_image", "message": "Uploaded image is empty."})
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"status": "image_too_large", "message": f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit."},
        )
    concept_list = [c.strip() for c in concepts.split(",")] if concepts else None
    try:
        return await scan_hazards(
            image_bytes,
            media_type=file.content_type,
            filename=file.filename,
            concepts=concept_list,
        )
    except RuntimeError as exc:  # MODEL_API_KEY missing (config.get_async_meta_client)
        raise HTTPException(
            status_code=503,
            detail={"status": "model_api_key_missing", "message": str(exc)},
        ) from exc
    except ValueError as exc:  # undecodable image / invalid concept list
        raise HTTPException(status_code=400, detail={"status": "invalid_scan_request", "message": str(exc)}) from exc


class TriageTextRequest(BaseModel):
    """Day 3 JSON text-fallback request (no audio, no image - typed clients)."""

    text: str = Field(..., min_length=1, description="Typed field-responder report (text fallback).")
    scan_result: dict | None = Field(default=None, description="Day 2 /api/scan-hazards JSON payload, if available.")
    scan_id: str | None = Field(default=None, description="Optional scan identifier carried into grounding/trace.")


def _meta_error(exc: Exception) -> HTTPException:
    """Map Meta-service failures to judge-safe HTTP errors (never leak the key)."""
    if isinstance(exc, RuntimeError) and "MODEL_API_KEY" in str(exc):
        return HTTPException(status_code=503, detail={"status": "model_api_key_missing", "message": str(exc)})
    if isinstance(exc, TranscriptionError):
        return HTTPException(
            status_code=502,
            detail={"status": "transcription_failed", "upstream_status": exc.status_code, "message": str(exc)},
        )
    if isinstance(exc, TriageParseError):
        return HTTPException(status_code=502, detail={"status": "triage_parse_failed", "message": str(exc)})
    if isinstance(exc, DispatchParseError):
        return HTTPException(status_code=502, detail={"status": "dispatch_parse_failed", "message": str(exc)})
    return HTTPException(status_code=502, detail={"status": "triage_upstream_failed", "message": str(exc)})


@app.get("/api/triage/readiness")
def triage_readiness() -> dict:
    """Day 3 input contract: WAV radio and/or text fallback + optional Day 2 scan."""
    return {
        "models": {"transcription": TRANSCRIBE_MODEL, "triage": TRIAGE_MODEL},
        "audio": {
            "field": "audio",
            "format": "WAV mono s16le at 16000 or 24000 Hz",
            "max_bytes": MAX_AUDIO_BYTES,
            "endpoint": "POST https://api.meta.ai/v1/asr/transcribe (via backend)",
        },
        "text_fallback": {"field": "text", "note": "Clean typed field report for browser testing without audio."},
        "grounding": {
            "scan_json_field": "scan_json (Day 2 /api/scan-hazards payload as JSON string)",
            "scan_id_field": "scan_id",
            "image_field": "image (optional, for muse-spark-1.3 multimodal reasoning)",
        },
        "output": "Structured triage priorities + UNVERIFIED candidate evacuation corridors / landing zones (normalized 0-1 coordinates). Deterministic geometry verifier checks each candidate; nothing here is marked safe.",
    }


@app.post("/api/triage")
async def triage_endpoint(
    audio: UploadFile | None = File(default=None, description="Field-radio WAV (mono s16le, 16000 or 24000 Hz)."),
    text: str | None = Form(default=None, description="Text fallback / supplemental operator note."),
    scan_json: str | None = Form(default=None, description="Day 2 scan payload as a JSON string."),
    scan_id: str | None = Form(default=None, description="Optional scan identifier."),
    image: UploadFile | None = File(default=None, description="Optional disaster image for multimodal triage."),
) -> dict:
    """Day 3: radio/text field report (+ optional scan/image) -> structured triage.

    muse-voice-transcribe-1.0 transcribes WAV audio (text fallback when no
    audio), then muse-spark-1.3 returns ranked priorities and candidate
    evacuation corridors / landing zones in normalized coordinates.
    Candidates are UNVERIFIED until the Day 4 deterministic verifier runs.
    """
    scan_result: dict | None = None
    if scan_json:
        try:
            parsed_scan = json.loads(scan_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400, detail={"status": "invalid_scan_json", "message": f"scan_json is not valid JSON: {exc}"}
            ) from exc
        if not isinstance(parsed_scan, dict):
            raise HTTPException(status_code=400, detail={"status": "invalid_scan_json", "message": "scan_json must be a JSON object (Day 2 scan payload)."})
        scan_result = parsed_scan

    audio_bytes: bytes | None = None
    audio_filename = "field-radio.wav"
    if audio is not None and audio.filename:
        audio_bytes = await audio.read()
        audio_filename = audio.filename
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail={"status": "audio_too_large", "message": f"Audio exceeds {MAX_AUDIO_BYTES // (1024 * 1024)} MB limit."})

    image_bytes: bytes | None = None
    image_media_type: str | None = None
    image_filename: str | None = None
    if image is not None and image.filename:
        image_bytes = await image.read()
        image_media_type = image.content_type
        image_filename = image.filename
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail={"status": "image_too_large", "message": f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit."})

    if not audio_bytes and not (text and text.strip()):
        raise HTTPException(
            status_code=400,
            detail={"status": "missing_field_report", "message": "Provide a field-radio WAV in 'audio' or a typed report in 'text'."},
        )
    try:
        return await run_triage(
            text=text,
            audio_bytes=audio_bytes,
            audio_filename=audio_filename,
            scan_result=scan_result,
            scan_id=scan_id,
            image_bytes=image_bytes,
            image_media_type=image_media_type,
            image_filename=image_filename,
        )
    except ValueError as exc:  # bad WAV, empty report, undecodable image
        raise HTTPException(status_code=400, detail={"status": "invalid_triage_request", "message": str(exc)}) from exc
    except (RuntimeError, TriageParseError) as exc:
        raise _meta_error(exc) from exc


@app.post("/api/triage/text")
async def triage_text_endpoint(payload: TriageTextRequest) -> dict:
    """Day 3 JSON variant of the text fallback (no audio/image upload)."""
    try:
        return await run_triage(text=payload.text, scan_result=payload.scan_result, scan_id=payload.scan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"status": "invalid_triage_request", "message": str(exc)}) from exc
    except (RuntimeError, TriageParseError) as exc:
        raise _meta_error(exc) from exc


class VerifyRequest(BaseModel):
    """Day 4: verify Day 3 candidates against the Day 2 scan, deterministically."""

    scan_result: dict = Field(..., description="Day 2 /api/scan-hazards payload (hazard/safe boxes + masks).")
    triage_result: dict | None = Field(default=None, description="Day 3 /api/triage payload carrying the candidates.")
    candidate_evacuation_corridors: list[dict] | None = Field(default=None, description="Explicit corridor candidates (override triage_result).")
    candidate_landing_zones: list[dict] | None = Field(default=None, description="Explicit landing-zone candidates (override triage_result).")
    latitude: float | None = Field(default=None, ge=-90, le=90, description="Optional scene latitude for OSM facilities (never derived from image coords).")
    longitude: float | None = Field(default=None, ge=-180, le=180, description="Optional scene longitude for OSM facilities.")
    facility_radius_m: int = Field(default=5000, ge=100, le=50000)
    auto_correct: bool = Field(default=True, description="Force muse-spark-1.3 re-route when a candidate is rejected (>10% hazard intersection by default).")
    max_correction_attempts: int = Field(default=2, ge=0, le=3)
    max_hazard_intersection_ratio: float = Field(default=DEFAULT_MAX_HAZARD_INTERSECTION, ge=0, le=1)
    min_safe_support_ratio: float = Field(default=0.5, ge=0, le=1)
    min_safe_surface_overlap_ratio: float = Field(default=0.5, ge=0, le=1)


@app.get("/api/verify/readiness")
def verify_readiness() -> dict:
    """Day 4 trust contract: deterministic geometry first, model second."""
    return {
        "engine": "deterministic_python (no model calls inside geometry)",
        "thresholds": {
            "max_hazard_intersection_ratio": DEFAULT_MAX_HAZARD_INTERSECTION,
            "rule": "hazard intersection > 10% rejects the candidate and forces a muse-spark-1.3 re-route",
            "min_safe_support_ratio": 0.5,
            "min_safe_surface_overlap_ratio": 0.5,
        },
        "methods": "mask IoU when SAM RLE decodes (integer/COCO counts), otherwise exact bbox geometry (declared in trace)",
        "facilities": {"provider": "OpenStreetMap Overpass API", "endpoint": OVERPASS_ENDPOINT,
                       "note": "Queried only when latitude/longitude are supplied; context only."},
        "output": "verified (green) or rejected (red) per candidate with geometric proof; only verified candidates are dispatch-ready.",
    }


@app.post("/api/verify")
async def verify_endpoint(payload: VerifyRequest) -> dict:
    """Day 4: deterministic verification + bounded Spark self-correction.

    The verifier computes hazard bbox/mask IoU and landing-zone clearance in
    pure local Python. If any candidate intersects a hazard by >10% (or fails
    support/clearance), muse-spark-1.3 must propose a re-route and the
    verifier re-checks it - the model never grades its own homework.
    """
    if (payload.latitude is None) != (payload.longitude is None):
        raise HTTPException(status_code=400, detail={"status": "invalid_coordinates", "message": "Provide both latitude and longitude, or neither."})
    try:
        return await run_verification_loop(
            payload.scan_result,
            triage_result=payload.triage_result,
            corridors=payload.candidate_evacuation_corridors,
            landing_zones=payload.candidate_landing_zones,
            latitude=payload.latitude,
            longitude=payload.longitude,
            facility_radius_m=payload.facility_radius_m,
            auto_correct=payload.auto_correct,
            max_correction_attempts=payload.max_correction_attempts,
            max_hazard_intersection=payload.max_hazard_intersection_ratio,
            min_safe_support=payload.min_safe_support_ratio,
            min_safe_surface_overlap=payload.min_safe_surface_overlap_ratio,
        )
    except ValueError as exc:  # empty scan, bad coordinates
        raise HTTPException(status_code=400, detail={"status": "invalid_verify_request", "message": str(exc)}) from exc
    except RuntimeError as exc:  # MODEL_API_KEY missing during a forced re-route
        raise _meta_error(exc) from exc


class DispatchRequest(BaseModel):
    """Day 5: dispatch from Day 4-verified state only (never raw proposals)."""

    verification_result: dict | None = Field(default=None, description="Full Day 4 /api/verify payload (preferred input).")
    verified_candidates: dict | None = Field(default=None, description="Optional {corridors, landing_zones} verified block, if not using verification_result.")
    triage_result: dict | None = Field(default=None, description="Day 3 /api/triage payload for urgency context.")
    include_briefing_card: bool = Field(default=True, description="Generate the muse-image-1.0 tactical briefing card.")


@app.get("/api/dispatch/readiness")
def dispatch_readiness() -> dict:
    """Day 5 trust contract: Wonder sees verified candidates only."""
    return {
        "models": {"dispatch": DISPATCH_MODEL, "briefing_image": BRIEFING_MODEL},
        "reasoning": {"effort": "high"},
        "input": "Day 4 /api/verify payload (verification_result) or its verified_candidates block. "
                 "Every candidate is re-gated deterministically: it must carry a verification record "
                 "with hazard_intersection_ratio <= 10%.",
        "guardrail": "Deterministic Python re-checks every unit assignment after muse-wonder-1.0 answers: "
                     "units aimed at unverified/rejected candidate IDs are HELD, never dispatched.",
        "briefing_card": "muse-image-1.0 prompt is built by deterministic Python from verified facts only; "
                         "image failure degrades to status=failed, never a fabricated card.",
        "output": "Multi-unit dispatch protocol (medical, debris clearance, aerial, evacuation, logistics) "
                  "+ optional PNG briefing card (base64). Nothing is dispatched without a verified target.",
    }


@app.post("/api/dispatch")
async def dispatch_endpoint(payload: DispatchRequest) -> dict:
    """Day 5: verified corridors/zones -> multi-unit dispatch + briefing card.

    muse-wonder-1.0 (reasoning: high) receives ONLY candidates the Day 4
    deterministic verifier marked verified; a deterministic guardrail then
    holds any unit aimed at an unverified target before anything is
    presented as dispatched.
    """
    if payload.verification_result is None and payload.verified_candidates is None:
        raise HTTPException(
            status_code=400,
            detail={"status": "missing_verification",
                    "message": "Provide the Day 4 /api/verify payload as verification_result (or its verified_candidates block). Dispatch never runs on unverified candidates."},
        )
    try:
        return await run_dispatch(
            verification_result=payload.verification_result,
            verified_candidates=payload.verified_candidates,
            triage_result=payload.triage_result,
            include_briefing_card=payload.include_briefing_card,
        )
    except NoDispatchableCandidatesError as exc:  # zero verified targets - honest refusal
        raise HTTPException(status_code=422, detail={"status": "no_verified_candidates", "message": str(exc)}) from exc
    except DispatchParseError as exc:
        raise _meta_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"status": "invalid_dispatch_request", "message": str(exc)}) from exc
    except RuntimeError as exc:  # MODEL_API_KEY missing / Wonder transport failure
        raise _meta_error(exc) from exc


@app.post("/api/run-crisisgrid")
async def run_crisisgrid_endpoint(
    image: UploadFile = File(..., description="Disaster image (JPEG/PNG/WebP): aerial, drone, or street level."),
    audio: UploadFile | None = File(default=None, description="Field-radio WAV (mono s16le, 16000 or 24000 Hz)."),
    text: str | None = Form(default=None, description="Text fallback / supplemental operator note."),
    latitude: float | None = Form(default=None, description="Optional scene latitude for OSM facilities."),
    longitude: float | None = Form(default=None, description="Optional scene longitude for OSM facilities."),
    facility_radius_m: int = Form(default=5000, description="OSM emergency-facility search radius (metres)."),
    auto_correct: bool = Form(default=True, description="Force muse-spark-1.3 re-route when the verifier rejects a candidate."),
    max_correction_attempts: int = Form(default=2, description="Bounded self-correction attempts (0-3)."),
    include_briefing_card: bool = Form(default=True, description="Generate the muse-image-1.0 tactical briefing card."),
    concepts: str | None = Form(default=None, description="Optional comma-separated sam-3.1 concept override (one request per phrase)."),
) -> dict:
    """Day 5 unified pipeline: scan -> triage -> verify -> dispatch.

    One call runs Days 2-5 end to end and returns every stage payload plus
    a concatenated Verifiable Agent Trace. If no candidate verifies, the
    pipeline completes honestly with dispatch skipped - muse-wonder-1.0 is
    never called on unverified geometry.
    """
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail={"status": "empty_image", "message": "Uploaded image is empty."})
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"status": "image_too_large", "message": f"Image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit."},
        )

    audio_bytes: bytes | None = None
    audio_filename = "field-radio.wav"
    if audio is not None and audio.filename:
        audio_bytes = await audio.read()
        audio_filename = audio.filename
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"status": "audio_too_large", "message": f"Audio exceeds {MAX_AUDIO_BYTES // (1024 * 1024)} MB limit."},
            )

    if not audio_bytes and not (text and text.strip()):
        raise HTTPException(
            status_code=400,
            detail={"status": "missing_field_report", "message": "Provide a field-radio WAV in 'audio' or a typed report in 'text'."},
        )
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=400,
            detail={"status": "invalid_coordinates", "message": "Provide both latitude and longitude, or neither."},
        )

    concept_list = [c.strip() for c in concepts.split(",")] if concepts else None
    try:
        return await run_crisisgrid_pipeline(
            image_bytes,
            media_type=image.content_type,
            filename=image.filename,
            audio_bytes=audio_bytes,
            audio_filename=audio_filename,
            text=text,
            concepts=concept_list,
            latitude=latitude,
            longitude=longitude,
            facility_radius_m=facility_radius_m,
            auto_correct=auto_correct,
            max_correction_attempts=max_correction_attempts,
            include_briefing_card=include_briefing_card,
        )
    except (TriageParseError, DispatchParseError) as exc:
        raise _meta_error(exc) from exc
    except ValueError as exc:  # bad WAV, empty report, undecodable image, bad concepts
        raise HTTPException(status_code=400, detail={"status": "invalid_pipeline_request", "message": str(exc)}) from exc
    except RuntimeError as exc:  # MODEL_API_KEY missing / upstream transport failure
        raise _meta_error(exc) from exc


# --------------------------------------------------------------------------- #
# Day 7: damage delta, post-clearance re-verification, multi-sector ranking
# --------------------------------------------------------------------------- #
class DeltaRequest(BaseModel):
    """Day 7: two Day 2 scan payloads (before/after). Deterministic, no models."""

    scan_before: dict = Field(..., description="Pre-disaster (or pre-clearance) /api/scan-hazards payload.")
    scan_after: dict = Field(..., description="Post-disaster (or post-clearance) /api/scan-hazards payload.")
    iou_threshold: float = Field(default=0.10, ge=0.0, le=1.0, description="Min box IoU to call a detection persistent across frames.")


@app.post("/api/delta")
def delta_endpoint(payload: DeltaRequest) -> dict:
    """Day 7: before/after damage delta via greedy per-concept IoU matching.

    Highlights NEW hazards, CLEARED hazards and LOST passable infrastructure.
    The delta never verifies a route - clearance requires the Day 4 verifier
    on the after scan (POST /api/delta/verify-clearance).
    """
    try:
        return compute_damage_delta(payload.scan_before, payload.scan_after, iou_threshold=payload.iou_threshold)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"status": "invalid_delta_request", "message": str(exc)}) from exc


class ClearanceRequest(BaseModel):
    """Day 7: re-verify the same candidates against the AFTER scan only."""

    scan_after: dict = Field(..., description="Post-clearance /api/scan-hazards payload.")
    triage_result: dict | None = Field(default=None, description="Day 3 payload carrying the candidate corridors / landing zones.")
    candidate_evacuation_corridors: list[dict] | None = Field(default=None, description="Explicit candidate corridors (override triage_result).")
    candidate_landing_zones: list[dict] | None = Field(default=None, description="Explicit candidate landing zones (override triage_result).")
    verification_before: dict | None = Field(default=None, description="Day 4 /api/verify payload from before clearance, for status-change reporting.")


@app.post("/api/delta/verify-clearance")
def verify_clearance_endpoint(payload: ClearanceRequest) -> dict:
    """Day 7: post-clearance verification (Day 4 verifier, zero model calls).

    A corridor flips blocked -> verified ONLY here, by passing deterministic
    geometry against the new frame. No Spark re-route runs in this path.
    """
    try:
        return verify_clearance(
            payload.scan_after,
            triage_result=payload.triage_result,
            candidate_corridors=payload.candidate_evacuation_corridors,
            candidate_landing_zones=payload.candidate_landing_zones,
            verification_before=payload.verification_before,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"status": "invalid_clearance_request", "message": str(exc)}) from exc


class SectorRankRequest(BaseModel):
    """Day 7: multi-sector snapshots for deterministic dispatch prioritisation."""

    sectors: list[dict] = Field(..., description="Each sector: {sector_id/name, triage_result?, verify_result?, scan_result?}.")


@app.post("/api/sectors/rank")
def rank_sectors_endpoint(payload: SectorRankRequest) -> dict:
    """Day 7: rank sectors by a published deterministic score (zero model calls).

    Ranking orders the work only - Day 5 dispatch still requires Day 4
    verified candidates in whichever sector is acted on first.
    """
    try:
        return rank_sectors(payload.sectors)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"status": "invalid_sector_request", "message": str(exc)}) from exc


@app.get("/api/delta/readiness")
def delta_readiness() -> dict:
    """Day 7 trust contract: delta highlights change; only the verifier flips status."""
    return {
        "day": 7,
        "engine": "deterministic_python",
        "model_calls": 0,
        "delta": "POST /api/delta compares two Day 2 scans by greedy per-concept box IoU matching (persistent / new / cleared).",
        "clearance": "POST /api/delta/verify-clearance re-runs the Day 4 verifier on the AFTER scan; a flip to verified happens nowhere else.",
        "sectors": "POST /api/sectors/rank applies a published 0-100 formula (urgency/severity/people/hazard/access). Ranking never verifies a route.",
    }


# --------------------------------------------------------------------------- #
# Day 8: pre-loaded global disaster presets (1-click judge testing)
# --------------------------------------------------------------------------- #
@app.get("/api/presets")
def presets_endpoint() -> dict:
    """Day 8: preset metadata (imagery + field report per preset).

    Static and honest: presets contain no pre-baked results. Running one
    still executes the full live pipeline; it may honestly end rejected or
    completed_no_dispatch like any other input.
    """
    return list_presets()


@app.get("/api/presets/{preset_id}")
def preset_endpoint(preset_id: str) -> dict:
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail={"status": "preset_not_found", "message": f"Unknown preset '{preset_id}'. GET /api/presets lists the available presets."})
    return {"status": "ok", "day": 8, "preset": preset}
