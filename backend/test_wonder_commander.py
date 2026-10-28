"""Offline tests for the Day 5 dispatch commander + unified pipeline.

Run:  python backend/test_wonder_commander.py  (no key, no network)

Geometry is never faked: the Day 4 verifier runs for real in the pipeline
test. Meta boundaries (sam-3.1 / muse-spark-1.3 / muse-wonder-1.0 /
muse-image-1.0) are faked at their client boundaries.
"""
import asyncio
import base64
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.wonder_commander import (
    DispatchParseError,
    NoDispatchableCandidatesError,
    build_briefing_card_prompt,
    build_dispatch_context,
    extract_dispatchable_state,
    parse_wonder_dispatch,
    run_crisisgrid_pipeline,
    run_dispatch,
)

FAILURES = []


def expect(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILURES.append(label)


# --------------------------------------------------------------------------- #
# Fake Meta clients (client-boundary fakes; geometry/models logic stays real)
# --------------------------------------------------------------------------- #
class FakeResponse:
    def __init__(self, output_text):
        self.output_text = output_text


class _Responses:
    def __init__(self, handler):
        self._handler = handler

    async def create(self, **kwargs):
        return self._handler(kwargs)


class _Images:
    def __init__(self, handler):
        self._handler = handler

    async def generate(self, **kwargs):
        return self._handler(kwargs)


class FakeClient:
    def __init__(self, responses=None, images=None):
        self.responses = _Responses(responses) if responses else None
        self.images = _Images(images) if images else None

    async def close(self):
        pass


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"crisisgrid-briefing-card"
PNG_B64 = base64.b64encode(PNG_BYTES).decode()


def images_ok(kwargs):
    return SimpleNamespace(data=[SimpleNamespace(b64_json=PNG_B64, url=None)])


def images_boom(kwargs):
    raise RuntimeError("muse-image-1.0 exploded (fake)")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
VER = {
    "status": "partially_verified",
    "day": 4,
    "dispatch_ready": False,
    "verified_candidates": {
        "corridors": [{
            "id": "corridor-1", "name": "Main Street evac", "purpose": "evacuation",
            "points_norm": [{"x": 0.05, "y": 0.5}, {"x": 0.95, "y": 0.5}],
            "start_label": "West junction", "end_label": "East shelter",
            "rationale": "Along segmented road", "grounded_concepts": ["road"],
            "verification": {"hazard_intersection_ratio": 0.0, "safe_support_ratio": 1.0, "method": "bbox"},
        }],
        "landing_zones": [{
            "id": "landing-zone-1", "name": "School field LZ",
            "center_norm": {"x": 0.2, "y": 0.82}, "radius_norm": 0.08,
            "surface_concept": "clear flat ground", "zone_type": "",
            "verification": {"hazard_intersection_ratio": 0.0, "hazard_iou": 0.0, "method": "bbox",
                             "clearance": {"zone_kind": "drone", "effective_radius_px": 80.0}},
        }],
    },
    "rejected_candidates": {
        "corridors": [{"candidate_id": "corridor-9", "kind": "evacuation_corridor",
                       "status": "rejected", "hazard_intersection_ratio": 0.61,
                       "reasons": ["Hazard intersection 61.0% exceeds 10% threshold (flood water)."]}],
        "landing_zones": [],
    },
    "emergency_facilities": {
        "status": "ok",
        "facilities": [{"name": "City Hospital", "type": "hospital", "distance_m": 1200.0}],
        "counts_by_type": {"hospital": 1},
    },
}

TRIAGE = {
    "status": "ok", "day": 3,
    "triage": {
        "incident_type": "urban flood", "severity": "critical", "urgency_score": 88,
        "summary": "Flooded corridor with stranded residents; main street passable.",
        "people_at_risk": {"count_estimate": 3, "description": "Family on rooftop", "confidence": 0.8},
        "hazards_identified": ["flood water", "debris"],
        "passable_infrastructure": ["road"],
        "blocked_infrastructure": ["bridge"],
        "priorities": [{"rank": 1, "category": "medical", "action": "Reach rooftop family",
                        "rationale": "Reported injuries", "target_concepts": ["road"], "location_hint": None}],
    },
}

WONDER_PAYLOAD = {
    "operation_name": "Operation Dry Corridor",
    "command_summary": "Medical + aerial response along the verified Main Street corridor.",
    "situation_assessment": "One corridor and one drone LZ verified; flood crossing rejected.",
    "units": [
        {"unit_id": "alpha", "unit_type": "Medical Team", "task": "Triage rooftop family",
         "target_candidate_id": "corridor-1", "target_kind": "area_support", "staging": "West junction",
         "priority_rank": 1, "eta_minutes_estimate": 12, "rationale": "Verified road corridor"},
        {"unit_id": "bravo", "unit_type": "aerial", "task": "Supply drop at LZ",
         "target_candidate_id": "landing-zone-1", "target_kind": "landing_zone", "staging": "East shelter",
         "priority_rank": 2, "eta_minutes_estimate": "soon", "rationale": "Verified drone LZ"},
        {"unit_id": "charlie", "unit_type": "rescue", "task": "Cross the flood block",
         "target_candidate_id": "corridor-9", "target_kind": "evacuation_corridor", "staging": "West junction",
         "priority_rank": 3, "eta_minutes_estimate": 5, "rationale": "Shortcut (must be held)"},
        {"unit_id": "delta", "unit_type": "logistics", "task": "",
         "target_candidate_id": None, "target_kind": "area_support", "staging": "",
         "priority_rank": 4, "eta_minutes_estimate": -3, "rationale": "No task (must be held)"},
        {"unit_id": "alpha", "unit_type": "evacuation", "task": "Shuttle evacuees east",
         "target_candidate_id": "corridor-1", "target_kind": "evacuation_corridor", "staging": "West junction",
         "priority_rank": 5, "eta_minutes_estimate": 20, "rationale": "Duplicate id (must be renamed)"},
    ],
    "phases": [{"phase": 1, "name": "Immediate life safety", "actions": ["Alpha moves on corridor-1"]}],
    "safety_brief": ["Stay on verified corridor-1 only"],
    "communications_plan": "Radio check every 10 minutes",
    "logistics_notes": ["Stage water at East shelter"],
    "assumptions": ["Road remains passable"],
    "confidence": 1.4,
}


def make_wonder_client(captured=None, payload=None):
    def handler(kwargs):
        if captured is not None:
            captured.update(kwargs)
        return FakeResponse(json.dumps(payload if payload is not None else WONDER_PAYLOAD))
    return FakeClient(responses=handler)


def _missing_key_factory():
    raise RuntimeError("MODEL_API_KEY is not set. Copy .env.example to .env and set MODEL_API_KEY.")


async def main() -> int:
    print("[Day 5] wonder_commander offline tests (faked model boundaries)")

    # --- Deterministic gate: only verifier-verified candidates enter ---
    state = extract_dispatchable_state(VER)
    expect([c["id"] for c in state["corridors"]] == ["corridor-1"], "gate admits verified corridor")
    expect([z["id"] for z in state["landing_zones"]] == ["landing-zone-1"], "gate admits verified LZ")
    expect(state["rejected_candidate_ids"] == ["corridor-9"], "rejected IDs tracked for exclusion")
    expect(state["dispatch_basis"] == "verified_subset_with_exclusions", "partial verify -> verified-subset basis")

    tampered = {"verified_candidates": {"corridors": [
        {"id": "corridor-x", "verification": {"hazard_intersection_ratio": 0.42, "method": "bbox"}}],
        "landing_zones": []}}
    state2 = extract_dispatchable_state(tampered)
    expect(not state2["corridors"] and state2["excluded"][0]["candidate_id"] == "corridor-x",
           "record with 42% hazard ratio fails the dispatch gate")
    unverified = {"verified_candidates": {"corridors": [{"id": "corridor-y"}], "landing_zones": []}}
    state3 = extract_dispatchable_state(unverified)
    expect(not state3["corridors"] and "missing Day 4 verification" in state3["excluded"][0]["reason"],
           "candidate without verification record excluded")

    # --- Context: rejected geometry never reaches Wonder ---
    context = build_dispatch_context(state, triage_result=TRIAGE, verification_result=VER)
    expect([c["id"] for c in context["verified_corridors"]] == ["corridor-1"], "context carries verified corridor only")
    expect(context["excluded_rejected_candidate_ids"] == ["corridor-9"], "context lists rejected ID as excluded")
    expect(context["mission"]["severity"] == "critical", "triage urgency context carried")
    expect(context["emergency_facilities"][0]["name"] == "City Hospital", "OSM facility context carried")

    # --- Full dispatch: guardrail holds unverified targets ---
    captured: dict = {}
    result = await run_dispatch(
        VER, triage_result=TRIAGE,
        wonder_client=make_wonder_client(captured), image_client=FakeClient(images=images_ok))
    expect(result["status"] == "ok" and result["day"] == 5, "dispatch returns ok/Day 5")
    expect(captured.get("model") == "muse-wonder-1.0", "Wonder model id used")
    expect(captured.get("reasoning") == {"effort": "high"}, "Wonder reasoning effort = high")
    roles = [m.get("role") for m in captured.get("input") or []]
    expect(roles == ["developer", "user"], "developer role preferred over system")
    sent = captured["input"][1]["content"][0]["text"]
    sent_ctx = json.loads(sent[sent.index("{"):sent.rindex("}") + 1])
    expect([c["id"] for c in sent_ctx["verified_corridors"]] == ["corridor-1"],
           "prompt contains ONLY verified corridor geometry")
    expect(sent_ctx["excluded_rejected_candidate_ids"] == ["corridor-9"], "prompt marks corridor-9 excluded")

    units = {u["unit_id"]: u for u in result["dispatch"]["units"]}
    expect(units["alpha"]["dispatch_status"] == "dispatched", "unit to verified corridor dispatched")
    expect(units["alpha"]["unit_type"] == "medical", "unit_type normalized (Medical Team -> medical)")
    expect(units["alpha"]["target_kind"] == "evacuation_corridor", "target kind corrected deterministically")
    expect(units["alpha"]["color"] == "#00C853", "dispatched renders green")
    expect(units["bravo"]["eta_minutes_estimate"] is None, "non-numeric ETA dropped, not invented")
    expect(units["charlie"]["dispatch_status"] == "held", "unit to REJECTED corridor held by guardrail")
    expect(units["charlie"]["target_candidate_id"] is None
           and units["charlie"]["requested_target_candidate_id"] == "corridor-9",
           "held unit target stripped, request preserved for audit")
    expect(units["charlie"]["color"] == "#FFD600", "held renders yellow, never green")
    expect(units["delta"]["dispatch_status"] == "held", "taskless unit held")
    expect("alpha-2" in units and units["alpha-2"]["dispatch_status"] == "dispatched",
           "duplicate unit_id renamed deterministically and dispatched")
    expect(result["guardrail"]["units_dispatched"] == 3 and result["guardrail"]["units_held"] == 2,
           "guardrail counts 3 dispatched / 2 held")
    expect(result["guardrail"]["model_calls"] == 0, "guardrail made zero model calls")
    expect(result["dispatch"]["confidence"] == 1.0, "confidence clamped to 1.0")
    expect(result["input_basis"]["dispatch_basis"] == "verified_subset_with_exclusions", "dispatch basis honest")

    # --- Briefing card: verified facts only, real base64 out ---
    card = result["briefing_card"]
    expect(card["status"] == "ok" and card["model"] == "muse-image-1.0", "briefing card generated via muse-image-1.0")
    expect(card["image_size_bytes"] == len(PNG_BYTES), "briefing PNG base64 decodes to real bytes")
    expect("corridor-1" in card["prompt"] and "Main Street evac" in card["prompt"],
           "card prompt names the verified corridor")
    expect("corridor-9" not in card["prompt"], "card prompt never mentions the rejected corridor")
    expect("VERIFIED ROUTES ONLY" in card["prompt"], "card prompt enforces verified-only footer")

    # --- Refusals: dispatch must never run without verified targets ---
    captured2: dict = {}
    try:
        await run_dispatch(
            {"status": "rejected", "verified_candidates": {"corridors": [], "landing_zones": []}},
            wonder_client=make_wonder_client(captured2))
        expect(False, "empty verified set refuses dispatch")
    except NoDispatchableCandidatesError:
        expect(True, "empty verified set refuses dispatch")
    expect(not captured2, "Wonder NOT called when nothing is verified")

    try:
        await run_dispatch(tampered, wonder_client=make_wonder_client())
        expect(False, "gate-excluded-only input refuses dispatch")
    except NoDispatchableCandidatesError:
        expect(True, "gate-excluded-only input refuses dispatch")

    # --- Parse discipline: bad Wonder output is an error, never a fake plan ---
    expect(parse_wonder_dispatch("```json\n" + json.dumps(WONDER_PAYLOAD) + "\n```").operation_name
           == "Operation Dry Corridor", "fenced Wonder JSON parses")
    try:
        parse_wonder_dispatch("the commander radioed static")
        expect(False, "non-JSON Wonder output raises DispatchParseError")
    except DispatchParseError:
        expect(True, "non-JSON Wonder output raises DispatchParseError")
    try:
        await run_dispatch(VER, wonder_client=FakeClient(responses=lambda kw: FakeResponse("garbage")),
                           include_briefing_card=False)
        expect(False, "run_dispatch propagates DispatchParseError")
    except DispatchParseError:
        expect(True, "run_dispatch propagates DispatchParseError")

    # --- Missing key: clear RuntimeError, no silent fallback provider ---
    try:
        await run_dispatch(VER, wonder_client_factory=_missing_key_factory)
        expect(False, "missing MODEL_API_KEY raises RuntimeError")
    except RuntimeError as exc:
        expect("MODEL_API_KEY" in str(exc), "missing MODEL_API_KEY raises RuntimeError")

    # --- Briefing card failure degrades; skip is explicit ---
    degraded = await run_dispatch(VER, wonder_client=make_wonder_client(),
                                  image_client=FakeClient(images=images_boom))
    expect(degraded["status"] == "ok" and degraded["briefing_card"]["status"] == "failed",
           "image failure degrades honestly; dispatch stands")
    skipped = await run_dispatch(VER, wonder_client=make_wonder_client(), include_briefing_card=False)
    expect(skipped["briefing_card"] is None
           and any(e["event"] == "briefing_card_skipped" for e in skipped["trace"]),
           "briefing card skip is explicit in trace")

    # --- Unified pipeline: scan -> triage -> verify -> dispatch (Days 2-5) ---
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1000, 1000), (110, 120, 130)).save(buf, format="JPEG")
    jpeg = buf.getvalue()

    sam_boxes = {"road": (0, 450, 1000, 550), "clear flat ground": (50, 700, 350, 950),
                 "flood water": (800, 50, 950, 200)}

    def sam_handler(kwargs):
        concept = kwargs["input"][0]["content"][0]["text"]
        box = sam_boxes.get(concept)
        if box is None:
            return FakeResponse("")
        x1, y1, x2, y2 = box
        return FakeResponse(f"<0f>0<|box;x1={x1};y1={y1};x2={x2};y2={y2};w=1000;h=1000|>")

    spark_triage = {
        "incident_type": "urban flood", "severity": "critical", "urgency_score": 88,
        "summary": "Flood block NE; main street passable; family stranded.",
        "people_at_risk": {"count_estimate": 3, "description": "Rooftop family", "confidence": 0.8},
        "hazards_identified": ["flood water"], "passable_infrastructure": ["road"],
        "blocked_infrastructure": [],
        "priorities": [{"rank": 1, "category": "medical", "action": "Reach rooftop family",
                        "rationale": "Radio report", "target_concepts": ["road"], "location_hint": None}],
        "candidate_evacuation_corridors": [{
            "id": "corridor-1", "name": "Main Street evac", "purpose": "evacuation",
            "points_norm": [[0.05, 0.5], [0.95, 0.5]], "start_label": "West junction",
            "end_label": "East shelter", "rationale": "Along road", "grounded_concepts": ["road"]}],
        "candidate_landing_zones": [{
            "id": "landing-zone-1", "name": "School field LZ", "center_norm": [0.2, 0.82],
            "radius_norm": 0.08, "surface_concept": "clear flat ground",
            "rationale": "Flat ground", "grounded_concepts": ["clear flat ground"]}],
        "recommended_units": [], "missing_information": [], "assumptions": [], "confidence": 0.9,
    }
    pipeline_wonder = {
        "operation_name": "Operation Dry Corridor", "command_summary": "Verified dispatch.",
        "situation_assessment": "Corridor + LZ verified by deterministic Python.",
        "units": [
            {"unit_id": "u1", "unit_type": "medical", "task": "Triage rooftop family",
             "target_candidate_id": "corridor-1", "target_kind": "evacuation_corridor",
             "staging": "West junction", "priority_rank": 1, "eta_minutes_estimate": 10, "rationale": ""},
            {"unit_id": "u2", "unit_type": "aerial", "task": "Supply drop",
             "target_candidate_id": "landing-zone-1", "target_kind": "landing_zone",
             "staging": "East shelter", "priority_rank": 2, "eta_minutes_estimate": 15, "rationale": ""},
        ],
        "phases": [], "safety_brief": [], "communications_plan": "", "logistics_notes": [],
        "assumptions": [], "confidence": 0.9,
    }
    run = await run_crisisgrid_pipeline(
        jpeg, text="Mayday: family stranded on rooftop, main street passable.",
        scan_client=FakeClient(responses=sam_handler),
        spark_client=FakeClient(responses=lambda kw: FakeResponse(json.dumps(spark_triage))),
        wonder_client=FakeClient(responses=lambda kw: FakeResponse(json.dumps(pipeline_wonder))),
        image_client=FakeClient(images=images_ok),
    )
    expect(run["status"] == "ok" and run["day"] == 5, "pipeline completes ok")
    expect(run["stages"]["triage"]["severity"] == "critical", "pipeline triage severity flows")
    expect(run["stages"]["verification"]["verified"] == 2, "pipeline verifier verifies corridor + LZ for real")
    expect(run["stages"]["dispatch"]["units_dispatched"] == 2, "pipeline dispatches 2 units to verified targets")
    expect(run["briefing_card"]["status"] == "ok", "pipeline briefing card generated")
    expect(run["verification_status"] == "verified_dispatch_issued", "pipeline trust status honest")
    expect(len(run["trace"]) >= 15, "pipeline trace concatenates all stages")

    # --- Pipeline with only a hazard-crossing candidate: dispatch locked ---
    bad_triage = dict(spark_triage)
    bad_triage["candidate_evacuation_corridors"] = [{
        "id": "corridor-bad", "name": "Flood shortcut", "purpose": "evacuation",
        "points_norm": [[0.875, 0.0], [0.875, 0.3]], "start_label": "N", "end_label": "S",
        "rationale": "Straight line", "grounded_concepts": []}]
    bad_triage["candidate_landing_zones"] = []
    blocked = await run_crisisgrid_pipeline(
        jpeg, text="Water rising fast near the north block.",
        scan_client=FakeClient(responses=sam_handler),
        spark_client=FakeClient(responses=lambda kw: FakeResponse(json.dumps(bad_triage))),
        wonder_client=make_wonder_client(), image_client=FakeClient(images=images_ok),
        auto_correct=False,
    )
    expect(blocked["status"] == "completed_no_dispatch" and blocked["dispatch"] is None,
           "hazard-crossing-only pipeline dispatches NOTHING")
    expect(blocked["dispatch_block"]["status"] == "no_verified_candidates", "dispatch block reason explicit")
    expect(any(e["event"] == "dispatch_skipped" for e in blocked["trace"]),
           "trace proves Wonder was not called on unverified geometry")

    # --- Pipeline input validation happens before any model call ---
    try:
        await run_crisisgrid_pipeline(jpeg)
        expect(False, "pipeline requires a field report (audio or text)")
    except ValueError:
        expect(True, "pipeline requires a field report (audio or text)")

    print(f"\n{len(FAILURES)} failure(s)" if FAILURES else "\nALL DAY 5 TESTS PASSED")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
