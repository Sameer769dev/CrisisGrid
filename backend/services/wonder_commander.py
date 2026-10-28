"""Autonomous dispatch commander - Day 5 (Oct 31, 2026).

Meta Model API contract (AGENTS.md SS3.4-3.5, binding):
- Dispatch coordinator: muse-wonder-1.0 via
  client.responses.create(model="muse-wonder-1.0",
  reasoning={"effort": "high"}, input=[...]); role "developer" preferred
  over "system" (SS3.3 convention).
- Tactical briefing card: muse-image-1.0 via
  client.images.generate(model="muse-image-1.0", prompt="...",
  output_format="png").

Trust law (AGENTS.md SS4): Wonder receives ONLY candidates the Day 4
deterministic verifier marked verified. Every candidate is re-gated here
in pure Python (its `verification` record must exist and its
hazard-intersection ratio must be <= the Day 4 threshold) before it may
enter the prompt. Rejected / unverified candidates never enter the
prompt as geometry - only their IDs are listed as excluded. After
Wonder answers, a deterministic guardrail re-validates every unit
assignment: a unit aimed at any candidate ID the verifier did not
verify is HELD, never dispatched. The briefing-card prompt is assembled
by deterministic Python from verified facts only, so the image model
cannot invent routes, hazards, or unit positions.
"""
from __future__ import annotations

import base64
import json
import re
import time
from typing import Any, Callable

from pydantic import BaseModel, Field, field_validator

try:  # repo-root imports (uvicorn backend.main:app)
    from backend.config import get_async_meta_client
    from backend.services.sam_hazard_scanner import extract_output_text, scan_hazards
    from backend.services.verifiable_corridor_engine import (
        DEFAULT_MAX_HAZARD_INTERSECTION,
        run_verification_loop,
    )
    from backend.services.voice_and_triage import run_triage
except ImportError:  # backend/ imports (uvicorn main:app, tests)
    from config import get_async_meta_client
    from services.sam_hazard_scanner import extract_output_text, scan_hazards
    from services.verifiable_corridor_engine import (
        DEFAULT_MAX_HAZARD_INTERSECTION,
        run_verification_loop,
    )
    from services.voice_and_triage import run_triage

DISPATCH_MODEL = "muse-wonder-1.0"
BRIEFING_MODEL = "muse-image-1.0"

# Unit vocabulary mirrors the Day 3 triage categories (voice_and_triage).
UNIT_TYPES = (
    "medical", "rescue", "debris_clearance", "aerial",
    "evacuation", "logistics", "infrastructure", "general",
)

VERIFIED_COLOR = "#00C853"   # dispatched to a verified target (Day 6 canvas)
HELD_COLOR = "#FFD600"       # held by the guardrail - caution, never green
MAX_PRIORITIES_IN_CONTEXT = 6
MAX_FACILITIES_IN_CONTEXT = 10


class DispatchParseError(ValueError):
    """muse-wonder-1.0 returned output that is not valid dispatch JSON."""


class NoDispatchableCandidatesError(ValueError):
    """No verifier-verified candidates exist, so dispatch must not run."""


# --------------------------------------------------------------------------- #
# muse-wonder-1.0 output schema (validated deterministically)
# --------------------------------------------------------------------------- #
class DispatchUnit(BaseModel):
    unit_id: str = ""
    unit_type: str = "general"  # one of UNIT_TYPES
    task: str = ""
    target_candidate_id: str | None = None
    target_kind: str = ""       # evacuation_corridor | landing_zone | area_support
    staging: str = ""
    priority_rank: int | None = None
    eta_minutes_estimate: int | None = None
    rationale: str = ""

    @field_validator("unit_type", mode="before")
    @classmethod
    def _unit_type(cls, v: Any) -> str:
        kind = str(v or "general").strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {"medical_team": "medical", "debris": "debris_clearance",
                   "clearance": "debris_clearance", "air": "aerial", "air_support": "aerial"}
        kind = aliases.get(kind, kind)
        return kind if kind in UNIT_TYPES else "general"

    @field_validator("eta_minutes_estimate", mode="before")
    @classmethod
    def _eta(cls, v: Any) -> int | None:
        if v is None:
            return None
        try:
            eta = int(round(float(v)))
        except (TypeError, ValueError):
            return None
        return eta if eta >= 0 else None


class DispatchPhase(BaseModel):
    phase: int = 0
    name: str = ""
    actions: list[str] = Field(default_factory=list)


class WonderDispatchPlan(BaseModel):
    operation_name: str = ""
    command_summary: str = ""
    situation_assessment: str = ""
    units: list[DispatchUnit] = Field(default_factory=list)
    phases: list[DispatchPhase] = Field(default_factory=list)
    safety_brief: list[str] = Field(default_factory=list)
    communications_plan: str = ""
    logistics_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v: Any) -> float:
        try:
            value = float(v or 0)
        except (TypeError, ValueError):
            value = 0.0
        return round(min(1.0, max(0.0, value)), 4)


# --------------------------------------------------------------------------- #
# Deterministic verified-state gate (pure Python - no model calls)
# --------------------------------------------------------------------------- #
def _verification_gate(candidate: dict[str, Any], max_hazard_intersection: float) -> str | None:
    """Return None if the candidate carries a passing Day 4 record, else why not."""
    verification = candidate.get("verification")
    if not isinstance(verification, dict):
        return "missing Day 4 verification record"
    ratio = verification.get("hazard_intersection_ratio")
    if not isinstance(ratio, (int, float)):
        return "verification record has no hazard_intersection_ratio"
    if float(ratio) > max_hazard_intersection + 1e-9:
        return (f"verification hazard ratio {float(ratio):.3f} exceeds "
                f"{max_hazard_intersection:.0%} dispatch gate")
    return None


def _dig_candidates(payload: dict[str, Any] | None) -> tuple[list, list, list[str]]:
    """Pull (corridors, landing_zones, rejected_ids) out of a Day 4 payload.

    Accepts the full /api/verify response, a verify_candidates payload, or
    a bare {"corridors": [...], "landing_zones": [...]} verified block.
    """
    if not isinstance(payload, dict):
        return [], [], []
    verified = payload.get("verified_candidates")
    if not isinstance(verified, dict):
        final = payload.get("final_verification")
        if isinstance(final, dict):
            verified = final.get("verified_candidates")
    if not isinstance(verified, dict):
        verified = payload if ("corridors" in payload or "landing_zones" in payload) else {}
    corridors = [c for c in (verified.get("corridors") or []) if isinstance(c, dict)]
    zones = [z for z in (verified.get("landing_zones") or []) if isinstance(z, dict)]

    rejected_ids: list[str] = []
    rejected = payload.get("rejected_candidates")
    if not isinstance(rejected, dict):
        final = payload.get("final_verification")
        rejected = final.get("rejected_candidates") if isinstance(final, dict) else None
    if isinstance(rejected, dict):
        for kind in ("corridors", "landing_zones"):
            for record in rejected.get(kind) or []:
                if isinstance(record, dict) and record.get("candidate_id"):
                    rejected_ids.append(str(record["candidate_id"]))
    return corridors, zones, rejected_ids


def extract_dispatchable_state(
    verification_result: dict[str, Any] | None = None,
    *,
    verified_candidates: dict[str, Any] | None = None,
    verified_corridors: list[dict[str, Any]] | None = None,
    verified_landing_zones: list[dict[str, Any]] | None = None,
    max_hazard_intersection: float = DEFAULT_MAX_HAZARD_INTERSECTION,
) -> dict[str, Any]:
    """Deterministic gate: only Day 4-verified candidates may be dispatched to.

    Every candidate - however it was supplied - must carry a verification
    record whose hazard-intersection ratio passes the Day 4 threshold.
    Anything else is excluded with a reason; nothing is silently trusted.
    """
    corridors_raw, zones_raw, rejected_ids = _dig_candidates(verification_result)
    if isinstance(verified_candidates, dict):
        corridors_raw += [c for c in (verified_candidates.get("corridors") or []) if isinstance(c, dict)]
        zones_raw += [z for z in (verified_candidates.get("landing_zones") or []) if isinstance(z, dict)]
    if verified_corridors:
        corridors_raw += [c for c in verified_corridors if isinstance(c, dict)]
    if verified_landing_zones:
        zones_raw += [z for z in verified_landing_zones if isinstance(z, dict)]

    corridors, zones, excluded = [], [], []
    seen: set[str] = set()
    for kind, raw_list, out in (("evacuation_corridor", corridors_raw, corridors),
                                ("landing_zone", zones_raw, zones)):
        for candidate in raw_list:
            candidate_id = str(candidate.get("id") or "")
            if not candidate_id or candidate_id in seen:
                continue
            seen.add(candidate_id)
            reason = _verification_gate(candidate, max_hazard_intersection)
            if reason is None:
                out.append(candidate)
            else:
                excluded.append({"candidate_id": candidate_id, "kind": kind, "reason": reason})
    return {
        "corridors": corridors,
        "landing_zones": zones,
        "excluded": excluded,
        "rejected_candidate_ids": rejected_ids,
        "dispatch_basis": ("fully_verified"
                           if not rejected_ids and not excluded
                           else "verified_subset_with_exclusions"),
    }


# --------------------------------------------------------------------------- #
# Deterministic context builders (pure Python - no model calls)
# --------------------------------------------------------------------------- #
def _triage_context(triage_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(triage_result, dict):
        return None
    nested = triage_result.get("triage")
    triage = nested if isinstance(nested, dict) else triage_result
    if not any(k in triage for k in ("severity", "urgency_score", "priorities", "summary")):
        return None
    return {
        "incident_type": triage.get("incident_type"),
        "severity": triage.get("severity"),
        "urgency_score": triage.get("urgency_score"),
        "summary": triage.get("summary"),
        "people_at_risk": triage.get("people_at_risk"),
        "hazards_identified": list(triage.get("hazards_identified") or []),
        "priorities": list(triage.get("priorities") or [])[:MAX_PRIORITIES_IN_CONTEXT],
    }


def _facility_context(
    verification_result: dict[str, Any] | None,
    facilities: Any,
) -> list[dict[str, Any]]:
    raw = facilities
    if raw is None and isinstance(verification_result, dict):
        block = verification_result.get("emergency_facilities")
        if isinstance(block, dict) and block.get("status") == "ok":
            raw = block.get("facilities")
    if isinstance(raw, dict):
        raw = raw.get("facilities") if raw.get("status") == "ok" else []
    context = []
    for facility in raw or []:
        if not isinstance(facility, dict):
            continue
        context.append({
            "name": facility.get("name") or "unnamed facility",
            "type": facility.get("type") or facility.get("amenity") or "facility",
            "distance_m": facility.get("distance_m"),
        })
    return context[:MAX_FACILITIES_IN_CONTEXT]


def build_dispatch_context(
    verified_state: dict[str, Any],
    *,
    triage_result: dict[str, Any] | None = None,
    verification_result: dict[str, Any] | None = None,
    facilities: Any = None,
) -> dict[str, Any]:
    """The ONLY operating picture muse-wonder-1.0 is allowed to see."""
    corridors = []
    for candidate in verified_state["corridors"]:
        verification = candidate.get("verification") or {}
        corridors.append({
            "id": candidate.get("id"),
            "kind": "evacuation_corridor",
            "name": candidate.get("name") or "",
            "purpose": candidate.get("purpose") or "evacuation",
            "points_norm": candidate.get("points_norm") or [],
            "start": candidate.get("start_label") or "",
            "end": candidate.get("end_label") or "",
            "hazard_intersection_ratio": verification.get("hazard_intersection_ratio"),
            "safe_support_ratio": verification.get("safe_support_ratio"),
            "verification_method": verification.get("method"),
        })
    zones = []
    for candidate in verified_state["landing_zones"]:
        verification = candidate.get("verification") or {}
        clearance = verification.get("clearance") or {}
        zones.append({
            "id": candidate.get("id"),
            "kind": "landing_zone",
            "name": candidate.get("name") or "",
            "center_norm": candidate.get("center_norm"),
            "radius_norm": candidate.get("radius_norm"),
            "aircraft": clearance.get("zone_kind") or candidate.get("zone_type") or "drone",
            "surface_concept": candidate.get("surface_concept") or "",
            "hazard_intersection_ratio": verification.get("hazard_intersection_ratio"),
            "clearance_effective_radius_px": clearance.get("effective_radius_px"),
            "verification_method": verification.get("method"),
        })
    return {
        "mission": _triage_context(triage_result),
        "verified_corridors": corridors,
        "verified_landing_zones": zones,
        "excluded_rejected_candidate_ids": list(verified_state["rejected_candidate_ids"]),
        "emergency_facilities": _facility_context(verification_result, facilities),
        "hard_constraints": [
            "Assign units ONLY to IDs in verified_corridors / verified_landing_zones.",
            "excluded_rejected_candidate_ids were REJECTED by the deterministic verifier; using one is forbidden.",
            "Coordinates are normalized image coordinates [0,1]; never invent place names, roads, or coordinates.",
            "Emergency facilities are staging/handoff context only, not dispatch targets.",
        ],
    }


# --------------------------------------------------------------------------- #
# muse-wonder-1.0 autonomous dispatch - AGENTS.md SS3.4
# --------------------------------------------------------------------------- #
_DEVELOPER_INSTRUCTIONS = """You are CrisisGrid's autonomous dispatch commander (muse-wonder-1.0, high-effort reasoning).
You receive a DETERMINISTICALLY VERIFIED operating picture: every corridor and landing zone listed was proved by a local Python verifier (hazard intersection at or below 10 percent of route, on segmented safe infrastructure, landing clearance checked in image pixels).

Rules:
- Return ONLY a single JSON object. No markdown, no commentary, no extra keys.
- Assign units ONLY to candidate IDs listed under verified_corridors or verified_landing_zones. IDs in excluded_rejected_candidate_ids were REJECTED by the verifier - assigning a unit to one is forbidden; a deterministic guardrail will hold any violating assignment.
- unit_type is one of: medical, rescue, debris_clearance, aerial, evacuation, logistics, infrastructure, general.
- Every unit needs a concrete task tied to the verified picture. eta_minutes_estimate is an ESTIMATE - if unsure, say so in the rationale. Never invent place names, roads, coordinates, people counts, hazards, or facilities that are not in the input.
- Sequence the response in phases: immediate life-safety first, then access/clearance, then sustained evacuation/logistics. The safety_brief must restate the verified hazard constraints (keep all units on verified routes/zones only).
- Emergency facilities are staging/handoff context only.

JSON schema (exact keys):
{
  "operation_name": "string",
  "command_summary": "2-3 sentence commander summary",
  "situation_assessment": "grounded assessment built only from the verified picture",
  "units": [{"unit_id": "unit-1", "unit_type": "medical", "task": "string", "target_candidate_id": "corridor-1 or null", "target_kind": "evacuation_corridor|landing_zone|area_support", "staging": "string", "priority_rank": 1, "eta_minutes_estimate": null, "rationale": "string"}],
  "phases": [{"phase": 1, "name": "Immediate life safety", "actions": ["string"]}],
  "safety_brief": ["verified hazard constraints every unit must obey"],
  "communications_plan": "string",
  "logistics_notes": ["string"],
  "assumptions": ["string"],
  "confidence": 0.0
}"""


def build_wonder_user_text(context: dict[str, Any]) -> str:
    return (
        "VERIFIED OPERATING PICTURE (deterministic Day 4 verifier output; "
        "rejected candidates appear as IDs only, with no geometry):\n"
        f"{json.dumps(context, indent=2)}\n\n"
        "Produce the autonomous multi-unit dispatch protocol as ONE JSON object. "
        "Dispatch only to verified candidate IDs."
    )


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_wonder_dispatch(output_text: str) -> WonderDispatchPlan:
    """Parse + validate Wonder's JSON. Deterministic; raises DispatchParseError."""
    text = _JSON_FENCE_RE.sub("", (output_text or "").strip())
    if not text:
        raise DispatchParseError("muse-wonder-1.0 returned empty output; no dispatch was fabricated.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise DispatchParseError(
                "muse-wonder-1.0 did not return JSON dispatch output. "
                f"First 300 chars: {text[:300]!r}"
            ) from None
        try:
            payload = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise DispatchParseError(f"muse-wonder-1.0 returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DispatchParseError("muse-wonder-1.0 dispatch JSON must be an object.")
    try:
        return WonderDispatchPlan.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError -> honest 502 upstream
        raise DispatchParseError(f"muse-wonder-1.0 dispatch JSON failed schema validation: {exc}") from exc


async def _close_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        result = close()
        if hasattr(result, "__await__"):
            await result


async def request_dispatch_plan(
    context: dict[str, Any],
    *,
    client: Any = None,
    client_factory: Callable[[], Any] | None = None,
) -> tuple[WonderDispatchPlan, float]:
    """Run muse-wonder-1.0 (reasoning effort high) on the verified picture."""
    active_client = client or (client_factory or get_async_meta_client)()
    close_when_done = client is None and client_factory is None
    started = time.perf_counter()
    try:
        response = await active_client.responses.create(
            model=DISPATCH_MODEL,
            reasoning={"effort": "high"},  # AGENTS.md SS3.4
            input=[
                {
                    "type": "message",
                    "role": "developer",  # AGENTS.md SS3.3: prefer developer over system
                    "content": [{"type": "input_text", "text": _DEVELOPER_INSTRUCTIONS}],
                },
                {"type": "message", "role": "user",
                 "content": [{"type": "input_text", "text": build_wonder_user_text(context)}]},
            ],
        )
    except Exception as exc:
        raise RuntimeError(f"muse-wonder-1.0 request failed: {exc}") from exc
    finally:
        if close_when_done:
            await _close_client(active_client)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    return parse_wonder_dispatch(extract_output_text(response)), latency_ms


# --------------------------------------------------------------------------- #
# Deterministic guardrail (pure Python - the model never grades itself)
# --------------------------------------------------------------------------- #
def sanitize_dispatch_plan(
    plan: WonderDispatchPlan,
    verified_state: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Hold any unit that targets a candidate the verifier did not verify."""
    kind_by_id = {c["id"]: "evacuation_corridor" for c in verified_state["corridors"]}
    kind_by_id.update({z["id"]: "landing_zone" for z in verified_state["landing_zones"]})

    data = plan.model_dump()
    guardrail_actions: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    units_out: list[dict[str, Any]] = []
    for index, unit in enumerate(data["units"], start=1):
        unit_id = str(unit.get("unit_id") or "").strip() or f"unit-{index}"
        if unit_id in seen_ids:
            seen_ids[unit_id] += 1
            renamed = f"{unit_id}-{seen_ids[unit_id]}"
            guardrail_actions.append({
                "unit_id": renamed, "action": "unit_id_deduplicated",
                "detail": f"Wonder reused unit_id '{unit_id}'; renamed to '{renamed}' deterministically.",
            })
            unit_id = renamed
        seen_ids.setdefault(unit_id, 1)
        unit["unit_id"] = unit_id

        flags: list[str] = []
        target = unit.get("target_candidate_id")
        if target:
            target = str(target)
            if target in kind_by_id:
                unit["target_candidate_id"] = target
                unit["target_kind"] = kind_by_id[target]  # never trust the model's kind label
            else:
                guardrail_actions.append({
                    "unit_id": unit_id, "action": "held_unverified_target",
                    "detail": (f"Unit '{unit_id}' targeted '{target}', which the Day 4 verifier "
                               "did not verify. Assignment HELD by deterministic guardrail."),
                })
                unit["requested_target_candidate_id"] = target
                unit["target_candidate_id"] = None
                unit["target_kind"] = ""
                flags.append("held_unverified_target")
        if not str(unit.get("task") or "").strip():
            guardrail_actions.append({
                "unit_id": unit_id, "action": "held_missing_task",
                "detail": f"Unit '{unit_id}' has no concrete task; held by deterministic guardrail.",
            })
            flags.append("held_missing_task")

        unit["dispatch_status"] = "held" if flags else "dispatched"
        unit["color"] = HELD_COLOR if flags else VERIFIED_COLOR
        unit["guardrail_flags"] = flags
        units_out.append(unit)

    data["units"] = units_out
    data["summary_counts"] = {
        "units_total": len(units_out),
        "units_dispatched": sum(1 for u in units_out if u["dispatch_status"] == "dispatched"),
        "units_held": sum(1 for u in units_out if u["dispatch_status"] == "held"),
    }
    return data, guardrail_actions


# --------------------------------------------------------------------------- #
# muse-image-1.0 tactical briefing card - AGENTS.md SS3.5
# --------------------------------------------------------------------------- #
def build_briefing_card_prompt(dispatch: dict[str, Any], context: dict[str, Any]) -> str:
    """Facts-only prompt: verified corridors/zones + dispatched units only."""
    mission = context.get("mission") or {}
    dispatched = [u for u in dispatch.get("units") or [] if u.get("dispatch_status") == "dispatched"]
    type_counts: dict[str, int] = {}
    for unit in dispatched:
        type_counts[unit["unit_type"]] = type_counts.get(unit["unit_type"], 0) + 1
    corridor_labels = "; ".join(
        f"{c['id']} ({c.get('name') or 'verified corridor'})"
        for c in context["verified_corridors"]) or "none verified"
    zone_labels = "; ".join(
        f"{z['id']} ({z.get('name') or 'verified landing zone'}, {z.get('aircraft', 'drone')})"
        for z in context["verified_landing_zones"]) or "none verified"
    unit_labels = ", ".join(
        f"{kind} x{count}" for kind, count in sorted(type_counts.items())) or "no units dispatched"
    hazards = ", ".join((mission.get("hazards_identified") or [])[:6]) or "none reported"
    urgency = mission.get("urgency_score")
    facts = [
        f"Operation: {dispatch.get('operation_name') or 'CrisisGrid response'}",
        f"Severity: {mission.get('severity') or 'unknown'} / urgency {urgency if urgency is not None else 'unknown'}/100",
        f"VERIFIED evacuation corridors (bold green #00C853 route arrows): {corridor_labels}",
        f"VERIFIED landing zones (green #00C853 circles labelled LZ): {zone_labels}",
        f"Dispatched response units (labelled unit chips): {unit_labels}",
        f"Known hazards kept OFF the routes (red #FF2D20 warning strip, symbols only): {hazards}",
    ]
    return (
        "High-contrast flat vector tactical rescue briefing card for an emergency "
        "operations centre. Neo-brutalist command poster: off-white #FAFAF5 background, "
        "thick black borders, hard offset shadows, zero gradients, no photorealism, no 3D. "
        "Top header band in black with white text: CRISISGRID TACTICAL BRIEFING. "
        "Centre: a simplified tactical map panel using ONLY the facts below - green "
        "#00C853 for verified routes and landing zones, red #FF2D20 only in a hazard "
        "warning strip, yellow #FFD600 for caution labels. Bottom footer strip in black "
        "with white text: VERIFIED ROUTES ONLY - CHECKED BY DETERMINISTIC VERIFIER. "
        "Do NOT invent roads, rivers, buildings, place names, coordinates, people, or "
        "extra units beyond these facts:\n" + "\n".join(f"- {fact}" for fact in facts)
    )


async def generate_briefing_card(
    prompt: str,
    *,
    client: Any = None,
    client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Generate the PNG briefing card. Failure degrades honestly, never fakes."""
    active_client = client or (client_factory or get_async_meta_client)()
    close_when_done = client is None and client_factory is None
    started = time.perf_counter()
    response, error = None, None
    try:
        response = await active_client.images.generate(
            model=BRIEFING_MODEL, prompt=prompt, output_format="png",
        )
    except Exception as exc:  # image failure must not sink a valid dispatch
        error = exc
    finally:
        if close_when_done:
            await _close_client(active_client)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    base = {"model": BRIEFING_MODEL, "format": "png", "prompt": prompt, "latency_ms": latency_ms}
    if error is not None:
        return {**base, "status": "failed", "image_base64": None, "image_url": None,
                "error": {"type": type(error).__name__, "message": str(error)[:500]}}

    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    item = data[0] if data else None
    b64 = getattr(item, "b64_json", None) or (item.get("b64_json") if isinstance(item, dict) else None)
    url = getattr(item, "url", None) or (item.get("url") if isinstance(item, dict) else None)
    image_size = None
    if b64:
        try:
            image_size = len(base64.b64decode(str(b64), validate=True))
        except Exception:
            return {**base, "status": "failed", "image_base64": None, "image_url": url,
                    "error": {"type": "InvalidImagePayload",
                              "message": "muse-image-1.0 returned undecodable base64; card not fabricated."}}
    if not b64 and not url:
        return {**base, "status": "failed", "image_base64": None, "image_url": None,
                "error": {"type": "EmptyImageResponse",
                          "message": "muse-image-1.0 returned no image payload; card not fabricated."}}
    return {**base, "status": "ok", "image_base64": b64, "image_url": url,
            "image_size_bytes": image_size, "error": None}


# --------------------------------------------------------------------------- #
# Orchestrator used by POST /api/dispatch
# --------------------------------------------------------------------------- #
async def run_dispatch(
    verification_result: dict[str, Any] | None = None,
    *,
    verified_candidates: dict[str, Any] | None = None,
    verified_corridors: list[dict[str, Any]] | None = None,
    verified_landing_zones: list[dict[str, Any]] | None = None,
    triage_result: dict[str, Any] | None = None,
    facilities: Any = None,
    include_briefing_card: bool = True,
    max_hazard_intersection: float = DEFAULT_MAX_HAZARD_INTERSECTION,
    wonder_client: Any = None,
    wonder_client_factory: Callable[[], Any] | None = None,
    image_client: Any = None,
    image_client_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Day 5 pipeline: verified state -> Wonder dispatch -> guardrail -> card."""
    started = time.perf_counter()
    trace: list[dict[str, Any]] = []

    state = extract_dispatchable_state(
        verification_result,
        verified_candidates=verified_candidates,
        verified_corridors=verified_corridors,
        verified_landing_zones=verified_landing_zones,
        max_hazard_intersection=max_hazard_intersection,
    )
    if not state["corridors"] and not state["landing_zones"]:
        raise NoDispatchableCandidatesError(
            "No Day 4-verified corridors or landing zones to dispatch to. "
            "Rejected and unverified candidates are never dispatched: run "
            "POST /api/verify and re-plan until at least one candidate verifies."
        )
    trace.append({
        "step": "verifier", "event": "dispatch_input_gate",
        "detail": (
            f"Deterministic gate admitted {len(state['corridors'])} verified corridor(s) and "
            f"{len(state['landing_zones'])} verified landing zone(s); "
            f"{len(state['rejected_candidate_ids'])} rejected candidate(s) excluded by ID, "
            f"{len(state['excluded'])} record(s) failed the verification gate."
        ),
        "state": "verified",
    })
    for excluded in state["excluded"]:
        trace.append({
            "step": "verifier", "event": "candidate_gate_excluded",
            "candidate_id": excluded["candidate_id"], "kind": excluded["kind"],
            "detail": f"{excluded['candidate_id']}: excluded from dispatch - {excluded['reason']}.",
            "state": "rejected",
        })

    context = build_dispatch_context(
        state, triage_result=triage_result,
        verification_result=verification_result, facilities=facilities,
    )
    plan, wonder_ms = await request_dispatch_plan(
        context, client=wonder_client, client_factory=wonder_client_factory)
    dispatch, guardrail_actions = sanitize_dispatch_plan(plan, state)
    counts = dispatch["summary_counts"]
    trace.append({
        "step": "muse-wonder-1.0", "event": "dispatch_proposed",
        "detail": (
            f"High-effort dispatch in {wonder_ms} ms: {counts['units_total']} unit(s) proposed "
            f"against {len(state['corridors']) + len(state['landing_zones'])} verified candidate(s)."
        ),
        "state": "info", "latency_ms": wonder_ms,
    })
    for action in guardrail_actions:
        trace.append({
            "step": "guardrail", "event": action["action"],
            "detail": action["detail"], "state": "caution",
        })
    trace.append({
        "step": "guardrail", "event": "dispatch_sanitized",
        "detail": (f"Deterministic guardrail (zero model calls): {counts['units_dispatched']} unit(s) "
                   f"dispatched to verified targets, {counts['units_held']} held."),
        "state": "verified" if counts["units_held"] == 0 else "caution",
    })

    briefing_card: dict[str, Any] | None = None
    if include_briefing_card:
        prompt = build_briefing_card_prompt(dispatch, context)
        briefing_card = await generate_briefing_card(
            prompt, client=image_client, client_factory=image_client_factory)
        if briefing_card["status"] == "ok":
            trace.append({
                "step": "muse-image-1.0", "event": "briefing_card_generated",
                "detail": (f"Tactical briefing card generated in {briefing_card['latency_ms']} ms "
                           "from verified facts only (no invented routes or units)."),
                "state": "info", "latency_ms": briefing_card["latency_ms"],
            })
        else:
            trace.append({
                "step": "muse-image-1.0", "event": "briefing_card_failed",
                "detail": (f"Briefing card failed ({briefing_card['error']['type']}: "
                           f"{briefing_card['error']['message']}). Dispatch stands; no image fabricated."),
                "state": "caution", "latency_ms": briefing_card["latency_ms"],
            })
    else:
        trace.append({
            "step": "muse-image-1.0", "event": "briefing_card_skipped",
            "detail": "Briefing card not requested for this dispatch.", "state": "info",
        })

    return {
        "status": "ok",
        "day": 5,
        "models": {"dispatch": DISPATCH_MODEL, "briefing_image": BRIEFING_MODEL},
        "reasoning": {"effort": "high"},
        "input_basis": {
            "verified_corridors": [c["id"] for c in state["corridors"]],
            "verified_landing_zones": [z["id"] for z in state["landing_zones"]],
            "excluded_rejected_candidate_ids": list(state["rejected_candidate_ids"]),
            "gate_excluded": state["excluded"],
            "dispatch_basis": state["dispatch_basis"],
        },
        "dispatch": dispatch,
        "guardrail": {
            "engine": "deterministic_python",
            "model_calls": 0,
            "actions": guardrail_actions,
            "units_dispatched": counts["units_dispatched"],
            "units_held": counts["units_held"],
        },
        "briefing_card": briefing_card,
        "trace": trace,
        "total_latency_ms": round((time.perf_counter() - started) * 1000, 1),
        # Trust law: dispatch flows from Day 4-verified state only.
        "verification_status": "dispatch_from_verified_candidates_only",
        "next_step": "Day 6: render dispatch + briefing card in the Tactical Command UI (Dispatch Action Console).",
    }


# --------------------------------------------------------------------------- #
# Unified pipeline used by POST /api/run-crisisgrid (Days 2-5 in one call)
# --------------------------------------------------------------------------- #
async def run_crisisgrid_pipeline(
    image_bytes: bytes,
    *,
    media_type: str | None = None,
    filename: str | None = None,
    audio_bytes: bytes | None = None,
    audio_filename: str = "field-radio.wav",
    text: str | None = None,
    scan_id: str | None = None,
    concepts: Any = None,
    latitude: float | None = None,
    longitude: float | None = None,
    facility_radius_m: int = 5000,
    auto_correct: bool = True,
    max_correction_attempts: int = 2,
    include_briefing_card: bool = True,
    scan_client: Any = None,
    spark_client: Any = None,
    wonder_client: Any = None,
    image_client: Any = None,
    asr_http_client: Any = None,
    osm_http_client: Any = None,
) -> dict[str, Any]:
    """Full CrisisGrid: scan -> triage -> verify -> dispatch (+ briefing card).

    Each stage keeps its own honest trace; stages are concatenated so the
    Day 6 Verifiable Agent Trace can audit the whole run end to end. If no
    candidate verifies, dispatch is skipped with an explicit reason -
    the pipeline never dispatches to an unverified corridor or zone.
    """
    if not image_bytes:
        raise ValueError("Empty image: upload a JPEG, PNG, or WebP disaster image.")
    if not audio_bytes and not (text or "").strip():
        raise ValueError(
            "Provide a field-radio WAV upload or the text fallback report (AGENTS.md SS3.2).")
    if (latitude is None) != (longitude is None):
        raise ValueError("Provide both latitude and longitude, or neither.")

    started = time.perf_counter()
    scan = await scan_hazards(
        image_bytes, media_type=media_type, filename=filename,
        concepts=concepts, client=scan_client)
    triage = await run_triage(
        text=text, audio_bytes=audio_bytes, audio_filename=audio_filename,
        scan_result=scan, scan_id=scan_id,
        image_bytes=image_bytes, image_media_type=media_type, image_filename=filename,
        spark_client=spark_client, asr_http_client=asr_http_client)
    verification = await run_verification_loop(
        scan, triage_result=triage,
        latitude=latitude, longitude=longitude, facility_radius_m=facility_radius_m,
        auto_correct=auto_correct, max_correction_attempts=max_correction_attempts,
        spark_client=spark_client, osm_http_client=osm_http_client)

    dispatch: dict[str, Any] | None = None
    dispatch_block: dict[str, Any] | None = None
    try:
        dispatch = await run_dispatch(
            verification_result=verification, triage_result=triage,
            include_briefing_card=include_briefing_card,
            wonder_client=wonder_client, image_client=image_client)
    except NoDispatchableCandidatesError as exc:
        dispatch_block = {"status": "no_verified_candidates", "message": str(exc)}

    trace = list(scan.get("trace") or []) + list(triage.get("trace") or []) \
        + list(verification.get("trace") or [])
    if dispatch is not None:
        trace += dispatch["trace"]
        dispatch_stage: dict[str, Any] = {
            "status": "ok",
            "units_dispatched": dispatch["guardrail"]["units_dispatched"],
            "units_held": dispatch["guardrail"]["units_held"],
            "briefing_card": (dispatch["briefing_card"] or {}).get("status"),
        }
    else:
        trace.append({
            "step": "muse-wonder-1.0", "event": "dispatch_skipped",
            "detail": ("No candidate survived deterministic verification, so "
                       "muse-wonder-1.0 was NOT called. Nothing was dispatched."),
            "state": "rejected",
        })
        dispatch_stage = {"status": "not_run_no_verified_candidates", **(dispatch_block or {})}

    verify_summary = (verification.get("final_verification") or {}).get("summary") or {}
    return {
        "status": "ok" if dispatch is not None else "completed_no_dispatch",
        "day": 5,
        "pipeline": ["sam-3.1 scan", "voice/text + muse-spark-1.3 triage",
                     "deterministic verification", "muse-wonder-1.0 dispatch"],
        "stages": {
            "scan": {
                "status": scan.get("status"),
                "detections": (scan.get("summary") or {}).get("total_detections"),
                "latency_ms": (scan.get("summary") or {}).get("total_latency_ms"),
            },
            "triage": {
                "severity": (triage.get("triage") or {}).get("severity"),
                "urgency_score": (triage.get("triage") or {}).get("urgency_score"),
                "candidate_corridors": len(triage.get("candidate_evacuation_corridors") or []),
                "candidate_landing_zones": len(triage.get("candidate_landing_zones") or []),
            },
            "verification": {
                "status": verification.get("status"),
                "verified": verify_summary.get("verified"),
                "rejected": verify_summary.get("rejected"),
                "dispatch_ready": verification.get("dispatch_ready"),
            },
            "dispatch": dispatch_stage,
        },
        "scan": scan,
        "triage": triage,
        "verification": verification,
        "dispatch": dispatch,
        "dispatch_block": dispatch_block,
        "briefing_card": dispatch["briefing_card"] if dispatch else None,
        "trace": trace,
        "total_latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "verification_status": (
            "verified_dispatch_issued" if dispatch is not None
            else "no_verified_candidates_nothing_dispatched"),
        "next_step": ("Day 6: render scan overlays, agent trace, and dispatch console in the "
                      "Tactical Command UI." if dispatch is not None else
                      "Re-plan candidates or supply a new scan; dispatch stays locked until "
                      "the deterministic verifier verifies at least one candidate."),
    }


# Friendly aliases
dispatch_verified = run_dispatch
run_crisisgrid = run_crisisgrid_pipeline
