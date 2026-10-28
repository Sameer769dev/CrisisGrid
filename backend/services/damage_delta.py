"""Day 7 (Nov 2, 2026): Before/After Damage Delta, post-clearance
re-verification, and Multi-Sector Triage ranking.

TRUST CONTRACT (AGENTS.md SS4): everything in this module is deterministic
local Python. ZERO model calls. A corridor or landing zone can only flip
from blocked -> verified here by being re-checked with the Day 4
deterministic verifier (`verify_candidates`) against a NEW scan - never by
comparing pictures and declaring a route safe.

Box matching between frames is greedy IoU matching per concept: a
post-disaster detection matched to a pre-disaster detection of the same
concept (IoU >= threshold) is PERSISTENT; an unmatched post detection is
NEW; an unmatched pre detection is CLEARED (hazards) or LOST (safe
infrastructure). Areas are box-area fractions of the frame; overlapping
boxes can sum past the true covered fraction, so area sums are labelled
box_area_fraction_sum exactly as in the Day 2 summary.
"""
from __future__ import annotations

import time
from typing import Any

try:  # package import (uvicorn backend.main:app / tests from repo root)
    from backend.services.verifiable_corridor_engine import (
        box_area,
        box_iou,
        extract_candidates,
        extract_scan_detections,
        verify_candidates,
    )
except ImportError:  # direct module import from backend/
    from services.verifiable_corridor_engine import (  # type: ignore
        box_area,
        box_iou,
        extract_candidates,
        extract_scan_detections,
        verify_candidates,
    )

MATCH_IOU_THRESHOLD = 0.10
SEVERITY_POINTS = {"critical": 25.0, "high": 18.0, "moderate": 10.0, "low": 4.0, "unknown": 0.0}


def _box_dict(box) -> dict[str, float]:
    return {"x_min": round(box[0], 6), "y_min": round(box[1], 6),
            "x_max": round(box[2], 6), "y_max": round(box[3], 6),
            "width": round(box[2] - box[0], 6), "height": round(box[3] - box[1], 6)}


def _match_concept(before: list[dict], after: list[dict], threshold: float):
    """Greedy IoU matching within one concept. Returns (pairs, only_before, only_after)."""
    scored = []
    for bi, b in enumerate(before):
        for ai, a in enumerate(after):
            iou = box_iou(b["box"], a["box"])
            if iou >= threshold:
                scored.append((iou, bi, ai))
    scored.sort(reverse=True)
    used_b, used_a, pairs = set(), set(), []
    for iou, bi, ai in scored:
        if bi in used_b or ai in used_a:
            continue
        used_b.add(bi); used_a.add(ai); pairs.append((before[bi], after[ai], iou))
    return pairs, [b for i, b in enumerate(before) if i not in used_b], [a for i, a in enumerate(after) if i not in used_a]


def compute_damage_delta(scan_before: dict[str, Any], scan_after: dict[str, Any],
                         *, iou_threshold: float = MATCH_IOU_THRESHOLD) -> dict[str, Any]:
    """Deterministic before/after comparison of two Day 2 scan payloads."""
    started = time.perf_counter()
    for label, scan in (("scan_before", scan_before), ("scan_after", scan_after)):
        if not isinstance(scan, dict) or not scan:
            raise ValueError(f"{label} must be a Day 2 /api/scan-hazards payload.")
    before, bw, bh = extract_scan_detections(scan_before)
    after, aw, ah = extract_scan_detections(scan_after)
    trace: list[dict[str, Any]] = [{
        "step": "delta", "event": "frames_loaded",
        "detail": (f"Before: {len(before)} detection(s) on {bw}x{bh}; after: {len(after)} detection(s) "
                   f"on {aw}x{ah}. Greedy per-concept IoU matching at >= {iou_threshold:.0%}; "
                   "deterministic Python, zero model calls."),
        "state": "info"}]
    warnings: list[str] = []
    if (bw, bh) != (aw, ah) and bw and aw:
        warnings.append(f"Frame sizes differ (before {bw}x{bh} vs after {aw}x{ah}); boxes are normalised 0-1 so comparison proceeds, but re-check framing before acting.")

    concepts = sorted({d["concept"] for d in before} | {d["concept"] for d in after})
    delta_detections: list[dict[str, Any]] = []
    per_concept: list[dict[str, Any]] = []
    totals = {"new_hazards": 0, "cleared_hazards": 0, "persistent_hazards": 0,
              "new_safe": 0, "lost_safe": 0, "persistent_safe": 0,
              "hazard_area_before": 0.0, "hazard_area_after": 0.0,
              "safe_area_before": 0.0, "safe_area_after": 0.0}

    for concept in concepts:
        b_list = [d for d in before if d["concept"] == concept]
        a_list = [d for d in after if d["concept"] == concept]
        kind = (a_list or b_list)[0]["kind"]
        pairs, only_b, only_a = _match_concept(b_list, a_list, iou_threshold)
        b_area = sum(box_area(d["box"]) for d in b_list)
        a_area = sum(box_area(d["box"]) for d in a_list)
        if kind == "hazard":
            totals["hazard_area_before"] += b_area; totals["hazard_area_after"] += a_area
            totals["new_hazards"] += len(only_a); totals["cleared_hazards"] += len(only_b); totals["persistent_hazards"] += len(pairs)
        elif kind == "safe_zone":
            totals["safe_area_before"] += b_area; totals["safe_area_after"] += a_area
            totals["new_safe"] += len(only_a); totals["lost_safe"] += len(only_b); totals["persistent_safe"] += len(pairs)

        def emit(det, status, match_iou, other_area):
            area = box_area(det["box"])
            # Render kind: what the operator must feel. A cleared hazard and a
            # new safe surface are good (green); a new hazard and a lost road
            # are bad (red); persistent keeps its semantic kind.
            if status == "persistent":
                render_kind = det["kind"]
            elif det["kind"] == "hazard":
                render_kind = "safe_zone" if status == "cleared" else "hazard"
            else:
                render_kind = "hazard" if status == "cleared" else "safe_zone"
            color = "#FF2D20" if render_kind == "hazard" else "#00C853"
            if status == "persistent":
                color = "#FFD600" if det["kind"] == "hazard" else "#00C853"
            delta_detections.append({
                "concept": concept, "kind": render_kind, "semantic_kind": det["kind"],
                "delta_status": status, "color": color,
                "bbox": _box_dict(det["box"]),
                "bbox_xyxy_norm": [round(v, 6) for v in det["box"]],
                "area_fraction": round(area, 6),
                "matched_iou": round(match_iou, 4) if match_iou is not None else None,
                "counterpart_area_fraction": round(other_area, 6) if other_area is not None else None,
                "has_mask": False, "mask": None})
        for b_det, a_det, iou in pairs:
            emit(a_det, "persistent", iou, box_area(b_det["box"]))
        for det in only_a:
            emit(det, "new", None, None)
        for det in only_b:
            emit(det, "cleared", None, None)
        per_concept.append({
            "concept": concept, "kind": kind,
            "before_count": len(b_list), "after_count": len(a_list),
            "persistent": len(pairs), "new": len(only_a), "cleared": len(only_b),
            "box_area_fraction_before": round(b_area, 6), "box_area_fraction_after": round(a_area, 6),
            "box_area_fraction_delta": round(a_area - b_area, 6)})
        if only_a or only_b:
            trace.append({"step": "delta", "event": f"concept_changed:{concept}", "concept": concept,
                          "detail": (f"{concept} ({kind}): {len(pairs)} persistent, {len(only_a)} new, "
                                     f"{len(only_b)} {'cleared' if kind == 'hazard' else 'lost'}; box area "
                                     f"{b_area:.1%} -> {a_area:.1%} of frame."),
                          "state": "caution" if (only_a and kind == "hazard") or (only_b and kind == "safe_zone") else "info"})

    hazard_delta = totals["hazard_area_after"] - totals["hazard_area_before"]
    safe_delta = totals["safe_area_after"] - totals["safe_area_before"]
    if totals["new_hazards"] or hazard_delta > 0.02:
        verdict = "worsened_new_damage"
    elif totals["cleared_hazards"] and hazard_delta < -0.02:
        verdict = "improved_hazards_cleared"
    elif not before and not after:
        verdict = "no_detections_either_frame"
    else:
        verdict = "broadly_stable"
    trace.append({"step": "delta", "event": f"verdict:{verdict}",
                  "detail": (f"Damage delta verdict: {verdict}. Hazard box area {totals['hazard_area_before']:.1%} -> "
                             f"{totals['hazard_area_after']:.1%}; passable box area {totals['safe_area_before']:.1%} -> "
                             f"{totals['safe_area_after']:.1%}. The delta highlights change only - it never verifies a route."),
                  "state": "verified" if verdict == "improved_hazards_cleared" else "caution" if verdict == "worsened_new_damage" else "info"})
    return {
        "status": "ok", "day": 7, "engine": "deterministic_python", "model_calls": 0,
        "match_iou_threshold": iou_threshold,
        "frames": {"before": {"detections": len(before), "width": bw or None, "height": bh or None},
                   "after": {"detections": len(after), "width": aw or None, "height": ah or None}},
        "warnings": warnings, "verdict": verdict,
        "summary": {**{k: (round(v, 6) if isinstance(v, float) else v) for k, v in totals.items()},
                    "hazard_area_delta": round(hazard_delta, 6), "safe_area_delta": round(safe_delta, 6)},
        "per_concept": per_concept, "delta_detections": delta_detections,
        "trace": trace, "total_latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "verification_status": "delta_only_not_a_route_verification",
        "next_step": "Re-run candidates through POST /api/delta/verify-clearance (Day 4 verifier on the AFTER scan) before treating any cleared corridor as usable."}

# --------------------------------------------------------------------------- #
# Post-clearance verification: same candidates, AFTER scan, Day 4 verifier only
# --------------------------------------------------------------------------- #
def _status_map(verification: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """candidate_id -> result from a Day 4 payload (loop or raw verify)."""
    if not isinstance(verification, dict):
        return {}
    final = verification.get("final_verification") if isinstance(verification.get("final_verification"), dict) else verification
    out: dict[str, dict[str, Any]] = {}
    for key in ("corridor_results", "landing_zone_results"):
        for r in final.get(key) or []:
            if r.get("candidate_id"):
                out[str(r["candidate_id"])] = r
    if not out:  # verified_candidates-only payload
        vc = verification.get("verified_candidates") or {}
        for kind_key in ("corridors", "landing_zones"):
            for c in vc.get(kind_key) or []:
                cid = str(c.get("id") or "")
                if cid:
                    ver = c.get("verification") or {}
                    out[cid] = {"candidate_id": cid, "status": "verified",
                                "hazard_intersection_ratio": ver.get("hazard_intersection_ratio", 0.0)}
    return out


def verify_clearance(scan_after: dict[str, Any], *, triage_result: dict[str, Any] | None = None,
                     candidate_corridors: list[dict[str, Any]] | None = None,
                     candidate_landing_zones: list[dict[str, Any]] | None = None,
                     verification_before: dict[str, Any] | None = None) -> dict[str, Any]:
    """Re-verify the SAME candidates against the AFTER (post-clearance) scan.

    Deterministic Day 4 verifier only - zero model calls, no Spark re-route:
    a flip to verified must be earned against the new frame, and the
    before/after status change for every candidate is reported explicitly.
    """
    started = time.perf_counter()
    corridors_in, zones_in = extract_candidates(triage_result, candidate_corridors, candidate_landing_zones)
    if not corridors_in and not zones_in:
        raise ValueError("No candidates to re-verify: pass triage_result or explicit candidate_corridors / candidate_landing_zones.")
    raw_corridors = [{k: v for k, v in c.items() if k != "points"} for c in corridors_in]
    raw_zones = [{k: v for k, v in z.items() if k != "center"} for z in zones_in]
    verification = verify_candidates(scan_after, corridors=raw_corridors, landing_zones=raw_zones)
    before_map = _status_map(verification_before)
    after_map = _status_map(verification)
    changes: list[dict[str, Any]] = []
    for cid in sorted(set(before_map) | set(after_map)):
        b, a = before_map.get(cid), after_map.get(cid)
        b_status = b.get("status") if b else "not_previously_verified"
        a_status = a.get("status") if a else "not_in_after_frame"
        changes.append({
            "candidate_id": cid,
            "kind": (a or b or {}).get("kind", ""),
            "before_status": b_status, "after_status": a_status,
            "before_hazard_intersection_ratio": b.get("hazard_intersection_ratio") if b else None,
            "after_hazard_intersection_ratio": a.get("hazard_intersection_ratio") if a else None,
            "flipped_to_verified": b_status != "verified" and a_status == "verified",
            "flipped_to_rejected": b_status == "verified" and a_status == "rejected",
            "reasons": (a or {}).get("reasons", [])})
    flipped = [c for c in changes if c["flipped_to_verified"]]
    still_blocked = [c for c in changes if c["after_status"] == "rejected"]
    if flipped and not still_blocked:
        verdict = "cleared_and_verified"
    elif flipped:
        verdict = "partially_cleared"
    elif still_blocked:
        verdict = "still_blocked"
    else:
        verdict = "no_status_change"
    trace = list(verification.get("trace") or [])
    trace.append({"step": "clearance", "event": f"verdict:{verdict}",
                  "detail": (f"Post-clearance re-verification on the AFTER scan (Day 4 verifier, zero model calls): "
                             f"{len(flipped)} candidate(s) flipped blocked -> VERIFIED, {len(still_blocked)} still REJECTED. "
                             "A candidate is usable only if its after_status is verified."),
                  "state": "verified" if verdict == "cleared_and_verified" else "caution" if flipped else "rejected" if still_blocked else "info"})
    wrapper = {
        "status": verification["status"], "day": 4, "engine": "deterministic_python",
        "model_calls_in_geometry": 0, "correction_model": None,
        "verified_candidates": verification["verified_candidates"],
        "rejected_candidates": verification["rejected_candidates"],
        "correction": {"enabled": False, "max_attempts": 0, "attempts_used": 0,
                       "status": "disabled_clearance_recheck", "history": []},
        "emergency_facilities": {"status": "not_queried", "facilities": [], "counts_by_type": {}},
        "final_verification": verification, "trace": trace,
        "total_latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "verification_status": "verified_by_deterministic_python" if verification["status"] == "verified" else "not_verified_rejected_or_partial",
        "dispatch_ready": verification["status"] == "verified",
        "next_step": "Only candidates with after_status=verified may flow into Day 5 dispatch."}
    return {
        "status": "ok", "day": 7, "engine": "deterministic_python", "model_calls": 0,
        "verdict": verdict, "status_changes": changes,
        "flipped_to_verified": [c["candidate_id"] for c in flipped],
        "still_blocked": [c["candidate_id"] for c in still_blocked],
        "verification": verification, "verification_result": wrapper,
        "trace": trace, "total_latency_ms": wrapper["total_latency_ms"],
        "verification_status": wrapper["verification_status"],
        "dispatch_ready": wrapper["dispatch_ready"],
        "next_step": wrapper["next_step"]}


# --------------------------------------------------------------------------- #
# Multi-Sector Triage: deterministic dispatch-priority ranking
# --------------------------------------------------------------------------- #
def _sector_facts(sector: dict[str, Any]) -> dict[str, Any]:
    triage = sector.get("triage_result") if isinstance(sector.get("triage_result"), dict) else {}
    t = triage.get("triage") if isinstance(triage.get("triage"), dict) else triage
    verify = sector.get("verify_result") or sector.get("verification_result") or {}
    final = verify.get("final_verification") if isinstance(verify.get("final_verification"), dict) else {}
    summary = final.get("summary") or verify.get("summary") or {}
    scan = sector.get("scan_result") if isinstance(sector.get("scan_result"), dict) else {}
    scan_summary = scan.get("summary") or {}
    hazards = scan_summary.get("hazards") or {}
    urgency = sector.get("urgency_score", t.get("urgency_score"))
    try:
        urgency = float(urgency) if urgency is not None else 0.0
    except (TypeError, ValueError):
        urgency = 0.0
    people = (t.get("people_at_risk") or {}).get("count_estimate") if isinstance(t.get("people_at_risk"), dict) else None
    return {
        "sector_id": str(sector.get("sector_id") or sector.get("id") or sector.get("name") or "sector"),
        "name": str(sector.get("name") or sector.get("sector_id") or "Sector"),
        "severity": str(t.get("severity") or sector.get("severity") or "unknown").lower(),
        "urgency_score": max(0.0, min(100.0, urgency)),
        "people_at_risk": people,
        "hazard_area_fraction_sum": float(hazards.get("box_area_fraction_sum") or sector.get("hazard_area_fraction_sum") or 0.0),
        "candidates_total": int(summary.get("total") or 0),
        "candidates_verified": int(summary.get("verified") or 0),
        "candidates_rejected": int(summary.get("rejected") or 0),
        "dispatch_ready": bool(verify.get("dispatch_ready")),
        "has_triage": bool(t), "has_verification": bool(verify)}


def rank_sectors(sectors: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank sectors for dispatch prioritisation. Deterministic, zero model calls.

    Score (0-100) = urgency*0.40 (max 40) + severity (max 25)
    + people-at-risk scaled to 50 people (max 15) + hazard footprint (max 10)
    + access pressure (max 10: blocked-with-candidates 10, dispatch-ready 6,
    unverified candidates 4). Every component is reported - no hidden weights.
    """
    started = time.perf_counter()
    if not isinstance(sectors, list) or not sectors:
        raise ValueError("sectors must be a non-empty list of sector snapshots.")
    ranked = []
    for sector in sectors:
        if not isinstance(sector, dict):
            raise ValueError("Each sector must be an object snapshot.")
        f = _sector_facts(sector)
        urgency_c = round(f["urgency_score"] * 0.40, 2)
        severity_c = SEVERITY_POINTS.get(f["severity"], 0.0)
        people_c = round(min(float(f["people_at_risk"]), 50.0) / 50.0 * 15.0, 2) if isinstance(f["people_at_risk"], (int, float)) else 0.0
        hazard_c = round(min(f["hazard_area_fraction_sum"], 0.5) / 0.5 * 10.0, 2)
        if f["candidates_rejected"] and not f["candidates_verified"]:
            access_c, access_note = 10.0, "all candidates blocked - clearance needed first"
        elif f["dispatch_ready"]:
            access_c, access_note = 6.0, "verified access - actionable now"
        elif f["candidates_total"]:
            access_c, access_note = 4.0, "candidates proposed, unverified"
        else:
            access_c, access_note = 0.0, "no candidates yet"
        score = round(urgency_c + severity_c + people_c + hazard_c + access_c, 2)
        if not f["has_triage"]:
            action = "needs_triage_first"
        elif f["dispatch_ready"]:
            action = "dispatch_now"
        elif f["candidates_rejected"] and not f["candidates_verified"]:
            action = "clearance_then_reverify"
        elif f["candidates_total"]:
            action = "verify_candidates"
        else:
            action = "propose_candidates"
        ranked.append({**f, "score": score, "recommended_action": action,
                       "breakdown": {"urgency_component": urgency_c, "severity_component": severity_c,
                                     "people_component": people_c, "hazard_component": hazard_c,
                                     "access_component": access_c, "access_note": access_note}})
    ranked.sort(key=lambda r: (-r["score"], r["sector_id"]))
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    trace = [{"step": "sectors", "event": "ranked",
              "detail": (f"{len(ranked)} sector(s) ranked deterministically (zero model calls). Top: "
                         + (f"{ranked[0]['sector_id']} score {ranked[0]['score']} -> {ranked[0]['recommended_action']}." if ranked else "none.")),
              "state": "info"}]
    return {"status": "ok", "day": 7, "engine": "deterministic_python", "model_calls": 0,
            "formula": "score = urgency*0.40 + severity(critical 25/high 18/moderate 10/low 4) + people(min(n,50)/50*15) + hazard(min(area,0.5)/0.5*10) + access(blocked 10 / dispatch-ready 6 / unverified 4)",
            "ranked_sectors": ranked, "trace": trace,
            "total_latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "verification_status": "ranking_only_dispatch_still_requires_day4_verified_candidates",
            "next_step": "Dispatch (Day 5) still only accepts Day 4-verified candidates per sector; ranking orders the work, it never verifies a route."}
