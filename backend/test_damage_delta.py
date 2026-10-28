"""Day 7 offline tests: damage delta, clearance flip, sector ranking.

Run from repo root:  python backend/test_damage_delta.py
No network, no MODEL_API_KEY: all geometry is deterministic local Python
and the clearance flip is earned through the real Day 4 verifier.
"""
import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.damage_delta import compute_damage_delta, rank_sectors, verify_clearance  # noqa: E402

passed = failed = 0

def expect(cond, label):
    global passed, failed
    if cond: passed += 1; print(f"  PASS {label}")
    else: failed += 1; print(f"  FAIL {label}")

def scan(dets, w=100, h=100):
    out = []
    for concept, kind, (x1, y1, x2, y2) in dets:
        out.append({"concept": concept, "kind": kind,
                    "bbox_xyxy_norm": [x1, y1, x2, y2],
                    "bbox": {"x_min": x1, "y_min": y1, "x_max": x2, "y_max": y2, "width": x2 - x1, "height": y2 - y1},
                    "bbox_px": {"x1": x1 * w, "y1": y1 * h, "x2": x2 * w, "y2": y2 * h},
                    "area_fraction": round((x2 - x1) * (y2 - y1), 6), "has_mask": False, "mask": None})
    return {"status": "ok", "image": {"width": w, "height": h}, "detections": out}

ROAD = ("road", "safe_zone", (0.05, 0.45, 0.95, 0.55))
DEBRIS = ("debris", "hazard", (0.40, 0.40, 0.60, 0.60))
CORRIDOR = [{"id": "corridor-1", "name": "Main St", "points_norm": [{"x": 0.1, "y": 0.5}, {"x": 0.9, "y": 0.5}],
             "status": "unverified_candidate"}]

def main():
    print("== delta: new / cleared / persistent ==")
    before = scan([("flood water", "hazard", (0.0, 0.0, 0.3, 0.3)), DEBRIS, ROAD,
                   ("bridge", "safe_zone", (0.7, 0.0, 0.9, 0.2))])
    after = scan([("flood water", "hazard", (0.02, 0.02, 0.32, 0.32)), ROAD,
                  ("fire", "hazard", (0.6, 0.6, 0.8, 0.85))])
    d = compute_damage_delta(before, after)
    by = {(x["concept"], x["delta_status"]) for x in d["delta_detections"]}
    expect(("flood water", "persistent") in by, "shifted flood matched persistent")
    expect(("debris", "cleared") in by, "vanished debris is cleared")
    expect(("fire", "new") in by, "new fire flagged new")
    expect(("bridge", "cleared") in by, "lost bridge reported (rendered red via semantic mapping)")
    bridge = next(x for x in d["delta_detections"] if x["concept"] == "bridge")
    expect(bridge["kind"] == "hazard" and bridge["semantic_kind"] == "safe_zone", "lost safe infrastructure renders hazard-red")
    debris = next(x for x in d["delta_detections"] if x["concept"] == "debris")
    expect(debris["kind"] == "safe_zone", "cleared hazard renders green")
    expect(d["summary"]["new_hazards"] == 1 and d["summary"]["cleared_hazards"] == 1, "summary counts new/cleared hazards")
    expect(d["model_calls"] == 0 and d["verification_status"].startswith("delta_only"), "delta makes zero model calls and never verifies")
    expect(d["verdict"] == "worsened_new_damage", "new fire verdict = worsened")

    print("== delta: cleared scene verdict ==")
    d2 = compute_damage_delta(scan([DEBRIS, ROAD]), scan([ROAD]))
    expect(d2["verdict"] == "improved_hazards_cleared", "debris removal verdict = improved")
    try:
        compute_damage_delta({}, after); expect(False, "empty before scan raises")
    except ValueError: expect(True, "empty before scan raises")

    print("== clearance: blocked -> verified only via Day 4 verifier ==")
    before_verify = None
    # status before: run real verifier through clearance fn against BEFORE scan with empty before-map
    pre = verify_clearance(scan([DEBRIS, ROAD]), candidate_corridors=CORRIDOR)
    expect(pre["status_changes"][0]["after_status"] == "rejected", "corridor rejected while debris blocks it")
    # Build a Day-4-shaped before payload from that result for change reporting
    before_payload = {"final_verification": pre["verification"]}
    post = verify_clearance(scan([ROAD]), candidate_corridors=CORRIDOR, verification_before=before_payload)
    ch = post["status_changes"][0]
    expect(ch["before_status"] == "rejected" and ch["after_status"] == "verified", "same corridor flips rejected -> verified on after scan")
    expect(ch["flipped_to_verified"] is True and post["verdict"] == "cleared_and_verified", "verdict cleared_and_verified")
    expect(post["dispatch_ready"] is True and post["verification_result"]["dispatch_ready"] is True, "clearance result is dispatch-ready (Day 5 contract shape)")
    expect(post["model_calls"] == 0, "clearance path makes zero model calls")
    still = verify_clearance(scan([DEBRIS, ROAD]), candidate_corridors=CORRIDOR, verification_before=before_payload)
    expect(still["verdict"] == "still_blocked" and still["flipped_to_verified"] == [], "no flip when debris still present in re-scan")
    try:
        verify_clearance(scan([ROAD])); expect(False, "clearance without candidates raises")
    except ValueError: expect(True, "clearance without candidates raises")

    print("== sectors: deterministic ranking ==")
    sectors = [
        {"sector_id": "sector-b", "name": "Riverside", "urgency_score": 30, "severity": "low",
         "triage_result": {"triage": {"severity": "low", "urgency_score": 30, "people_at_risk": {"count_estimate": 2}}},
         "verify_result": {"dispatch_ready": True, "final_verification": {"summary": {"total": 1, "verified": 1, "rejected": 0}}}},
        {"sector_id": "sector-a", "name": "Old Town", "urgency_score": 90, "severity": "critical",
         "triage_result": {"triage": {"severity": "critical", "urgency_score": 90, "people_at_risk": {"count_estimate": 40}}},
         "verify_result": {"dispatch_ready": False, "final_verification": {"summary": {"total": 2, "verified": 0, "rejected": 2}}},
         "scan_result": {"summary": {"hazards": {"box_area_fraction_sum": 0.4}}}},
    ]
    r = rank_sectors(sectors)
    expect(r["ranked_sectors"][0]["sector_id"] == "sector-a", "critical blocked sector ranks first")
    expect(r["ranked_sectors"][0]["recommended_action"] == "clearance_then_reverify", "blocked sector action = clearance then re-verify")
    expect(r["ranked_sectors"][1]["recommended_action"] == "dispatch_now", "verified sector action = dispatch now")
    top = r["ranked_sectors"][0]
    expect(abs(top["score"] - (36 + 25 + 12 + 8 + 10)) < 0.01, f"score formula transparent (got {top['score']})")
    expect(r["model_calls"] == 0, "ranking makes zero model calls")
    try:
        rank_sectors([]); expect(False, "empty sector list raises")
    except ValueError: expect(True, "empty sector list raises")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
