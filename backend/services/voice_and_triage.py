"""Voice radio transcription + multimodal triage - Day 3 (Oct 29, 2026).

Meta Model API contract (AGENTS.md SS3.2-3.3, binding):
- Transcription: muse-voice-transcribe-1.0 via
  POST https://api.meta.ai/v1/asr/transcribe (multipart form-data,
  request={"mode": "ENDPOINTING", "model": "muse-voice-transcribe-1.0",
  "audioEncoding": "WAV"} + audio=@file.wav). Live-probed Oct 29: the API
  accepts mono s16le WAV at 16000 or 24000 Hz only, so WAV headers are
  validated deterministically before any network call.
- Triage: muse-spark-1.3 via client.responses.create, "developer" role
  preferred over "system". Spark receives the transcript, an optional image,
  and a deterministic, mask-stripped summary of the Day 2 sam-3.1 scan.

Trust law (AGENTS.md SS4): Spark PROPOSES triage priorities and candidate
evacuation corridors / landing zones in normalized image coordinates.
Nothing in this module verifies safety - every candidate is emitted as
"unverified_candidate" for the Day 4 deterministic verifier, which alone
may mark a corridor or landing zone verified/safe.
"""
from __future__ import annotations

import base64
import io
import json
import re
import time
import wave
from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

try:  # repo-root imports (uvicorn backend.main:app)
    from backend.config import META_API_BASE_URL, MODEL_API_KEY, get_async_meta_client
    from backend.services.sam_hazard_scanner import extract_output_text, sniff_media_type
except ImportError:  # backend/ imports (uvicorn main:app, tests)
    from config import META_API_BASE_URL, MODEL_API_KEY, get_async_meta_client
    from services.sam_hazard_scanner import extract_output_text, sniff_media_type

TRANSCRIBE_MODEL = "muse-voice-transcribe-1.0"
TRIAGE_MODEL = "muse-spark-1.3"
ASR_ENDPOINT_PATH = "/asr/transcribe"
SUPPORTED_WAV_SAMPLE_RATES = (16000, 24000)
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # field-radio upload ceiling
MAX_TEXT_CHARS = 8000

# Unverified proposals render yellow on the Day 6 canvas (AGENTS.md SS6).
CANDIDATE_COLOR = "#FFD600"


class TranscriptionError(RuntimeError):
    """muse-voice-transcribe-1.0 call failed (carries HTTP status if any)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class TriageParseError(ValueError):
    """muse-spark-1.3 returned output that is not valid structured triage JSON."""


# --------------------------------------------------------------------------- #
# Deterministic helpers (pure - unit-testable without any model call)
# --------------------------------------------------------------------------- #
def probe_wav_format(audio_bytes: bytes) -> dict[str, Any]:
    """Parse a WAV header locally. Raises ValueError for non-WAV / bad WAV."""
    if len(audio_bytes) < 12 or audio_bytes[0:4] != b"RIFF" or audio_bytes[8:12] != b"WAVE":
        raise ValueError("Audio must be a WAV file (muse-voice-transcribe-1.0 audioEncoding=WAV).")
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
            return {
                "channels": wav.getnchannels(),
                "sample_rate_hz": wav.getframerate(),
                "bits_per_sample": wav.getsampwidth() * 8,
                "frames": wav.getnframes(),
                "duration_seconds": round(wav.getnframes() / max(1, wav.getframerate()), 3),
            }
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"Could not parse WAV header: {exc}") from exc


def validate_wav_for_asr(audio_bytes: bytes) -> dict[str, Any]:
    """Enforce the live-probed ASR contract: mono s16le WAV @ 16k or 24k Hz."""
    if not audio_bytes:
        raise ValueError("Empty audio: upload a field-radio WAV recording.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError(f"Audio exceeds {MAX_AUDIO_BYTES // (1024 * 1024)} MB limit.")
    info = probe_wav_format(audio_bytes)
    problems = []
    if info["channels"] != 1:
        problems.append(f"channels={info['channels']} (expected mono)")
    if info["bits_per_sample"] != 16:
        problems.append(f"bitsPerSample={info['bits_per_sample']} (expected 16 / s16le)")
    if info["sample_rate_hz"] not in SUPPORTED_WAV_SAMPLE_RATES:
        problems.append(
            f"sampleRate={info['sample_rate_hz']} (expected one of {SUPPORTED_WAV_SAMPLE_RATES})"
        )
    if problems:
        raise ValueError(
            "Unsupported WAV format for muse-voice-transcribe-1.0: "
            + ", ".join(problems)
            + ". Re-record or resample to mono s16le WAV at 16000 or 24000 Hz."
        )
    return info


def extract_transcript(payload: Any) -> str:
    """Deterministically pull transcript text out of an ASR JSON payload."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        parts = [extract_transcript(item) for item in payload]
        return " ".join(part for part in parts if part).strip()
    if isinstance(payload, dict):
        for key in ("transcript", "text", "transcription", "utterance", "result_text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        # Common segment shapes: {"segments": [{"text": ...}]}, {"results": ...}
        for key in ("segments", "results", "alternatives", "channels", "output", "result", "data"):
            if key in payload:
                text = extract_transcript(payload[key])
                if text:
                    return text
        # OpenAI-style choice/message nesting, just in case the shape shifts.
        for key in ("choices",):
            if key in payload:
                text = extract_transcript(payload[key])
                if text:
                    return text
    return ""


def summarize_scan(scan_result: dict[str, Any] | None, scan_id: str | None = None) -> dict[str, Any]:
    """Compact, deterministic, mask-free summary of a Day 2 scan for Spark.

    The bulky RLE mask payloads are stripped: Spark reasons over boxes and
    counts; the Day 4 verifier re-reads the full masks geometrically.
    """
    if not scan_result:
        return {"provided": False, "scan_id": scan_id}
    summary = scan_result.get("summary") or {}
    layers: list[dict[str, Any]] = []
    for layer in scan_result.get("concept_layers") or []:
        layers.append({
            "concept": layer.get("concept"),
            "kind": layer.get("kind"),
            "status": layer.get("status"),
            "detection_count": layer.get("detection_count", 0),
            "mask_count": layer.get("mask_count", 0),
            "boxes_norm": [
                d.get("bbox_xyxy_norm") for d in (layer.get("detections") or [])[:5]
            ],
            "area_fraction_sum": round(
                sum(d.get("area_fraction", 0.0) for d in layer.get("detections") or []), 6
            ),
        })
    if not layers:  # tolerate a bare detections[] payload
        by_concept: dict[str, dict[str, Any]] = {}
        for det in scan_result.get("detections") or []:
            entry = by_concept.setdefault(det.get("concept", "unknown"), {
                "concept": det.get("concept"), "kind": det.get("kind"), "status": "ok",
                "detection_count": 0, "mask_count": 0, "boxes_norm": [], "area_fraction_sum": 0.0,
            })
            entry["detection_count"] += 1
            entry["mask_count"] += 1 if det.get("has_mask") else 0
            if len(entry["boxes_norm"]) < 5:
                entry["boxes_norm"].append(det.get("bbox_xyxy_norm"))
            entry["area_fraction_sum"] = round(entry["area_fraction_sum"] + det.get("area_fraction", 0.0), 6)
        layers = list(by_concept.values())
    return {
        "provided": True,
        "scan_id": scan_id,
        "status": scan_result.get("status"),
        "model": scan_result.get("model"),
        "verification_status": scan_result.get("verification_status"),
        "image": scan_result.get("image"),
        "totals": {
            "total_detections": summary.get("total_detections", len(scan_result.get("detections") or [])),
            "total_masks": summary.get("total_masks"),
            "hazards": summary.get("hazards"),
            "safe_zones": summary.get("safe_zones"),
        },
        "concept_layers": layers,
        "concepts_with_detections": [
            layer["concept"] for layer in layers if layer.get("detection_count")
        ],
    }


# --------------------------------------------------------------------------- #
# Pydantic schema for Spark's structured triage output (AGENTS.md SS6)
# --------------------------------------------------------------------------- #
def _clamp(value: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, float(value)))


class NormPoint(BaseModel):
    """One normalized image coordinate (origin top-left, x right, y down)."""

    x: float
    y: float

    @field_validator("x", "y", mode="before")
    @classmethod
    def _clamp01(cls, v: Any) -> float:
        return round(_clamp(float(v), 0.0, 1.0), 6)

    @model_validator(mode="before")
    @classmethod
    def _from_seq(cls, data: Any) -> Any:
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return {"x": data[0], "y": data[1]}
        return data


class PeopleAtRisk(BaseModel):
    count_estimate: int | None = None
    description: str = ""
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v: Any) -> float:
        return round(_clamp(float(v or 0), 0.0, 1.0), 4)


class TriagePriority(BaseModel):
    rank: int = 0
    category: str = "general"  # medical | rescue | evacuation | debris_clearance | aerial | infrastructure | logistics
    action: str
    rationale: str = ""
    target_concepts: list[str] = Field(default_factory=list)
    location_hint: str | None = None


class RecommendedUnit(BaseModel):
    unit_type: str
    task: str = ""
    priority_rank: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _from_str(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"unit_type": data}
        return data


class CandidateCorridor(BaseModel):
    """Spark-proposed evacuation corridor. NEVER verified by this module."""

    id: str = ""
    name: str = ""
    purpose: str = "evacuation"
    points_norm: list[NormPoint] = Field(default_factory=list)
    start_label: str = ""
    end_label: str = ""
    rationale: str = ""
    grounded_concepts: list[str] = Field(default_factory=list)


class CandidateLandingZone(BaseModel):
    """Spark-proposed drone/helicopter landing zone. NEVER verified here."""

    id: str = ""
    name: str = ""
    center_norm: NormPoint
    radius_norm: float = 0.05
    surface_concept: str = ""
    rationale: str = ""
    grounded_concepts: list[str] = Field(default_factory=list)

    @field_validator("radius_norm", mode="before")
    @classmethod
    def _radius(cls, v: Any) -> float:
        return round(_clamp(float(v or 0.05), 0.005, 0.5), 6)


class TriageAssessment(BaseModel):
    """The exact JSON contract muse-spark-1.3 must return (nothing else)."""

    incident_type: str = "unknown"
    severity: str = "unknown"  # critical | high | moderate | low | unknown
    urgency_score: int = 0     # 0-100
    summary: str = ""
    people_at_risk: PeopleAtRisk = Field(default_factory=PeopleAtRisk)
    hazards_identified: list[str] = Field(default_factory=list)
    passable_infrastructure: list[str] = Field(default_factory=list)
    blocked_infrastructure: list[str] = Field(default_factory=list)
    priorities: list[TriagePriority] = Field(default_factory=list)
    candidate_evacuation_corridors: list[CandidateCorridor] = Field(default_factory=list)
    candidate_landing_zones: list[CandidateLandingZone] = Field(default_factory=list)
    recommended_units: list[RecommendedUnit] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("severity", mode="before")
    @classmethod
    def _severity(cls, v: Any) -> str:
        sev = str(v or "unknown").strip().lower()
        return sev if sev in ("critical", "high", "moderate", "low") else "unknown"

    @field_validator("urgency_score", mode="before")
    @classmethod
    def _score(cls, v: Any) -> int:
        return int(round(_clamp(float(v or 0), 0, 100)))

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v: Any) -> float:
        return round(_clamp(float(v or 0), 0.0, 1.0), 4)


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_spark_triage(output_text: str) -> TriageAssessment:
    """Parse + validate Spark's JSON. Deterministic; raises TriageParseError."""
    text = _JSON_FENCE_RE.sub("", (output_text or "").strip())
    if not text:
        raise TriageParseError("muse-spark-1.3 returned empty output; no triage was fabricated.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise TriageParseError(
                "muse-spark-1.3 did not return JSON triage output. "
                f"First 300 chars: {text[:300]!r}"
            ) from None
        try:
            payload = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise TriageParseError(f"muse-spark-1.3 returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TriageParseError("muse-spark-1.3 triage JSON must be an object.")
    try:
        return TriageAssessment.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError -> honest 502 upstream
        raise TriageParseError(f"muse-spark-1.3 triage JSON failed schema validation: {exc}") from exc


def normalize_assessment(assessment: TriageAssessment) -> dict[str, Any]:
    """Deterministic post-processing: ranks, candidate ids/status, colours."""
    data = assessment.model_dump()
    priorities = sorted(data["priorities"], key=lambda p: (p.get("rank") or 999))
    for i, priority in enumerate(priorities, start=1):
        priority["rank"] = i
        priority["category"] = str(priority.get("category") or "general").strip().lower()
    data["priorities"] = priorities

    corridors = []
    for i, corridor in enumerate(data["candidate_evacuation_corridors"], start=1):
        if len(corridor.get("points_norm") or []) < 2:
            continue  # a corridor needs at least a start and an end point
        corridor["id"] = corridor.get("id") or f"corridor-{i}"
        corridor["status"] = "unverified_candidate"
        corridor["color"] = CANDIDATE_COLOR
        corridor["coordinate_space"] = "normalized_image_0_1"
        corridor["requires_day4_verification"] = True
        corridors.append(corridor)
    data["candidate_evacuation_corridors"] = corridors

    zones = []
    for i, zone in enumerate(data["candidate_landing_zones"], start=1):
        zone["id"] = zone.get("id") or f"landing-zone-{i}"
        zone["status"] = "unverified_candidate"
        zone["color"] = CANDIDATE_COLOR
        zone["coordinate_space"] = "normalized_image_0_1"
        zone["requires_day4_verification"] = True
        zones.append(zone)
    data["candidate_landing_zones"] = zones
    return data


# --------------------------------------------------------------------------- #
# muse-voice-transcribe-1.0 (ASR) - AGENTS.md SS3.2
# --------------------------------------------------------------------------- #
async def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str = "field-radio.wav",
    api_key: str | None = None,
    base_url: str | None = None,
    http_client: httpx.AsyncClient | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Transcribe one field-radio WAV via POST {base}/asr/transcribe."""
    wav_info = validate_wav_for_asr(audio_bytes)
    key = (api_key if api_key is not None else MODEL_API_KEY or "").strip()
    if not key:
        raise RuntimeError(
            "MODEL_API_KEY is not set. Copy .env.example to .env and set "
            "MODEL_API_KEY=<your Meta Model API key>, then restart the backend."
        )
    url = f"{(base_url or META_API_BASE_URL).rstrip('/')}{ASR_ENDPOINT_PATH}"
    request_payload = {"mode": "ENDPOINTING", "model": TRANSCRIBE_MODEL, "audioEncoding": "WAV"}
    files = {
        "request": (None, json.dumps(request_payload), "application/json"),
        "audio": (filename or "field-radio.wav", audio_bytes, "audio/wav"),
    }
    headers = {"Authorization": f"Bearer {key}"}

    started = time.perf_counter()
    try:
        if http_client is not None:
            response = await http_client.post(url, headers=headers, files=files)
        else:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, files=files)
    except httpx.HTTPError as exc:
        raise TranscriptionError(f"muse-voice-transcribe-1.0 request failed: {exc}") from exc
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    body_text = response.text or ""
    payload: Any
    try:
        payload = response.json()
    except Exception:
        payload = body_text
    if response.status_code >= 400:
        raise TranscriptionError(
            f"muse-voice-transcribe-1.0 returned HTTP {response.status_code}: {body_text[:400]}",
            status_code=response.status_code,
        )
    transcript = extract_transcript(payload)
    if not transcript:
        raise TranscriptionError(
            "muse-voice-transcribe-1.0 returned no transcript text. "
            f"Response keys/shape: {str(payload)[:300]!r}"
        )
    return {
        "status": "ok",
        "model": TRANSCRIBE_MODEL,
        "source": "audio_transcription",
        "transcript": transcript,
        "latency_ms": latency_ms,
        "audio": {
            "filename": filename,
            "media_type": "audio/wav",
            "size_bytes": len(audio_bytes),
            "encoding": "WAV",
            **wav_info,
        },
        "raw_response": payload if isinstance(payload, (dict, list)) else {"text": body_text[:2000]},
    }


# --------------------------------------------------------------------------- #
# muse-spark-1.3 multimodal triage - AGENTS.md SS3.3
# --------------------------------------------------------------------------- #
_DEVELOPER_INSTRUCTIONS = """You are CrisisGrid's multimodal triage reasoner (muse-spark-1.3).
You fuse a field-responder radio transcript, an optional disaster image, and a deterministic sam-3.1 segmentation summary into ONE structured triage assessment.

Rules:
- Return ONLY a single JSON object. No markdown, no commentary, no extra keys.
- Ground every claim in the transcript, the image, or the sam-3.1 scan summary. Never invent hazards, people, roads, or place names that are not supported by the inputs. If something is unknown, list it in missing_information.
- Coordinates are normalized image coordinates in [0,1]: origin top-left, x grows right, y grows down. Propose candidate evacuation corridors as polylines of at least 2 points and candidate landing zones as center + radius, ONLY where the scan/image plausibly supports them (e.g. along segmented road / clear flat ground / rooftop, away from segmented hazards). These candidates are UNVERIFIED proposals - a deterministic verifier checks them next. Never call them safe or verified.
- urgency_score is an integer 0-100. severity is one of critical, high, moderate, low, unknown.
- priorities are ranked operational actions (rank 1 = first). Categories: medical, rescue, evacuation, debris_clearance, aerial, infrastructure, logistics, general.

JSON schema (exact keys):
{
  "incident_type": "string, e.g. urban flood / earthquake / wildfire / unknown",
  "severity": "critical|high|moderate|low|unknown",
  "urgency_score": 0,
  "summary": "2-3 sentence grounded situation summary",
  "people_at_risk": {"count_estimate": null, "description": "string", "confidence": 0.0},
  "hazards_identified": ["concepts or descriptions grounded in inputs"],
  "passable_infrastructure": ["grounded items"],
  "blocked_infrastructure": ["grounded items"],
  "priorities": [{"rank": 1, "category": "medical", "action": "string", "rationale": "string", "target_concepts": ["sam-3.1 concepts"], "location_hint": "string or null"}],
  "candidate_evacuation_corridors": [{"id": "corridor-1", "name": "string", "purpose": "evacuation", "points_norm": [[0.0, 0.0], [1.0, 1.0]], "start_label": "string", "end_label": "string", "rationale": "string", "grounded_concepts": ["road"]}],
  "candidate_landing_zones": [{"id": "landing-zone-1", "name": "string", "center_norm": [0.5, 0.5], "radius_norm": 0.05, "surface_concept": "clear flat ground", "rationale": "string", "grounded_concepts": ["clear flat ground"]}],
  "recommended_units": [{"unit_type": "medical team", "task": "string", "priority_rank": 1}],
  "missing_information": ["string"],
  "assumptions": ["string"],
  "confidence": 0.0
}"""


def build_triage_user_text(transcript: str, scan_summary: dict[str, Any]) -> str:
    return (
        "FIELD RESPONDER REPORT (transcript):\n"
        f"{transcript}\n\n"
        "DETERMINISTIC sam-3.1 SEGMENTATION SUMMARY (Day 2, mask payloads stripped; "
        "boxes are normalized [x_min, y_min, x_max, y_max]):\n"
        f"{json.dumps(scan_summary, indent=2)}\n\n"
        "Assess urgency, rank triage priorities, and propose candidate evacuation "
        "corridor polylines and candidate landing zones in normalized coordinates "
        "where grounded. Return ONLY the JSON object from your instructions."
    )


async def assess_triage(
    transcript: str,
    *,
    scan_result: dict[str, Any] | None = None,
    scan_id: str | None = None,
    image_bytes: bytes | None = None,
    image_media_type: str | None = None,
    client: Any = None,
    client_factory: Callable[[], Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], float]:
    """Run muse-spark-1.3 triage. Returns (triage_dict, scan_summary, latency_ms)."""
    transcript = (transcript or "").strip()
    if not transcript:
        raise ValueError("Empty field report: provide radio audio or the text fallback.")
    if len(transcript) > MAX_TEXT_CHARS:
        transcript = transcript[:MAX_TEXT_CHARS]

    scan_summary = summarize_scan(scan_result, scan_id=scan_id)
    user_content: list[dict[str, Any]] = [
        {"type": "input_text", "text": build_triage_user_text(transcript, scan_summary)}
    ]
    if image_bytes:
        media = sniff_media_type(image_bytes, image_media_type)
        data_url = f"data:{media};base64,{base64.b64encode(image_bytes).decode()}"
        user_content.append({"type": "input_image", "image_url": data_url})

    active_client = client or (client_factory or get_async_meta_client)()
    close_when_done = client is None and client_factory is None
    started = time.perf_counter()
    try:
        response = await active_client.responses.create(
            model=TRIAGE_MODEL,
            input=[
                {
                    "type": "message",
                    "role": "developer",  # AGENTS.md SS3.3: prefer developer over system
                    "content": [{"type": "input_text", "text": _DEVELOPER_INSTRUCTIONS}],
                },
                {"type": "message", "role": "user", "content": user_content},
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
    assessment = parse_spark_triage(extract_output_text(response))
    return normalize_assessment(assessment), scan_summary, latency_ms


# --------------------------------------------------------------------------- #
# Orchestrator used by POST /api/triage
# --------------------------------------------------------------------------- #
async def run_triage(
    *,
    text: str | None = None,
    audio_bytes: bytes | None = None,
    audio_filename: str = "field-radio.wav",
    scan_result: dict[str, Any] | None = None,
    scan_id: str | None = None,
    image_bytes: bytes | None = None,
    image_media_type: str | None = None,
    image_filename: str | None = None,
    spark_client: Any = None,
    spark_client_factory: Callable[[], Any] | None = None,
    asr_http_client: httpx.AsyncClient | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Day 3 pipeline: (audio -> ASR | text fallback) + scan -> Spark triage."""
    trace: list[dict[str, Any]] = []
    started = time.perf_counter()

    supplemental_text = (text or "").strip() or None
    transcription: dict[str, Any]
    if audio_bytes:
        transcription = await transcribe_audio(
            audio_bytes, filename=audio_filename, api_key=api_key,
            base_url=base_url, http_client=asr_http_client,
        )
        transcript = transcription["transcript"]
        if supplemental_text:
            transcript = f"{transcript}\n[Operator supplemental note: {supplemental_text}]"
        trace.append({
            "step": "muse-voice-transcribe-1.0", "event": "transcription_complete",
            "detail": (
                f"Field radio transcribed in {transcription['latency_ms']} ms "
                f"({transcription['audio']['duration_seconds']}s WAV @ "
                f"{transcription['audio']['sample_rate_hz']} Hz mono)."
            ),
            "state": "info", "latency_ms": transcription["latency_ms"],
        })
    elif supplemental_text:
        transcript = supplemental_text
        transcription = {
            "status": "ok", "model": None, "source": "text_fallback",
            "transcript": transcript, "latency_ms": 0.0, "audio": None, "raw_response": None,
        }
        trace.append({
            "step": "input", "event": "text_fallback_used",
            "detail": "No audio supplied - clean text-input fallback used for field report ingestion.",
            "state": "info", "latency_ms": 0.0,
        })
    else:
        raise ValueError("Provide a field-radio WAV upload or the text fallback report.")

    triage, scan_summary, spark_latency = await assess_triage(
        transcript,
        scan_result=scan_result, scan_id=scan_id,
        image_bytes=image_bytes, image_media_type=image_media_type,
        client=spark_client, client_factory=spark_client_factory,
    )
    trace.append({
        "step": "sam-3.1", "event": "scan_grounding_prepared",
        "detail": (
            f"Spatial scan grounding: {scan_summary['totals']['total_detections']} detection(s) across "
            f"{len(scan_summary.get('concepts_with_detections') or [])} concept(s); RLE masks stripped for reasoning."
            if scan_summary.get("provided") else
            "No spatial scan supplied - triage grounded in transcript/image only; scan requested in missing_information."
        ),
        "state": "info",
    })
    trace.append({
        "step": "muse-spark-1.3", "event": "triage_complete",
        "detail": (
            f"Severity {triage['severity']} / urgency {triage['urgency_score']}/100 in {spark_latency} ms: "
            f"{len(triage['priorities'])} prioritie(s), "
            f"{len(triage['candidate_evacuation_corridors'])} candidate corridor(s), "
            f"{len(triage['candidate_landing_zones'])} candidate landing zone(s) - all UNVERIFIED."
        ),
        "state": "info", "latency_ms": spark_latency,
    })
    trace.append({
        "step": "verification", "event": "candidates_marked_unverified",
        "detail": "Candidate corridors/landing zones are proposals only. Deterministic geometry verifier must verify or reject each before any dispatch.",
        "state": "caution",
    })

    total_ms = round((time.perf_counter() - started) * 1000, 1)
    return {
        "status": "ok",
        "day": 3,
        "models": {"transcription": TRANSCRIBE_MODEL, "triage": TRIAGE_MODEL},
        "input": {
            "source": transcription["source"],
            "has_audio": bool(audio_bytes),
            "has_image": bool(image_bytes),
            "image_filename": image_filename,
            "has_scan": bool(scan_summary.get("provided")),
            "scan_id": scan_id,
        },
        "transcription": transcription,
        "transcript": transcript,
        "triage": triage,
        # Top-level mirrors so the Day 6 canvas need not dig into triage{}.
        "candidate_evacuation_corridors": triage["candidate_evacuation_corridors"],
        "candidate_landing_zones": triage["candidate_landing_zones"],
        "grounding": {
            "scan": scan_summary,
            "grounded_concepts": scan_summary.get("concepts_with_detections") or [],
        },
        "trace": trace,
        "total_latency_ms": total_ms,
        # Trust law: triage proposes, Day 4 disposes.
        "verification_status": "unverified_triage_proposal",
        "next_step": "Deterministic geometry verifier checks every candidate corridor (hazard IoU) and landing zone (clearance area) before dispatch.",
    }


# Friendly aliases
triage_field_report = run_triage
transcribe_field_radio = transcribe_audio
