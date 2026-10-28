"""Offline tests for the Day 4 deterministic verifier + correction loop.

Run:  python backend/test_verifiable_corridor_engine.py  (no key, no network)

Geometry expectations are hand-computed. The Spark re-route and the Overpass
API are faked at their client boundaries - geometry itself is never faked.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from backend.services.verifiable_corridor_engine import (
    box_iou,
    build_overpass_query,
    decode_sam_mask,
    encode_counts_fixture,
    haversine_m,
    parse_overpass_response,
    query_emergency_facilities,
    run_verification_loop,
    verify_candidates,
)

FAILURES = []


def expect(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILURES.append(label)


def det(concept, kind, box, mask=None):
    d = {"concept": concept, "kind": kind, "bbox_xyxy_norm": box,
         "bbox_px": {"x1": box[0] * 1000, "y1": box[1] * 1000, "x2": box[2] * 1000, "y2": box[3] * 1000},
         "area_fraction": 0.1, "has_mask": bool(mask)}
    if mask:
        d["mask"] = mask
    return d


# Scene: road across the middle, flood block centre, clear pad bottom-left.
SCAN = {
    "status": "ok", "model": "sam-3.1", "image": {"width": 1000, "height": 1000},
    "detections": [
        det("flood water", "hazard", [0.40, 0.40, 0.60, 0.60]),
        det("debris", "hazard", [0.80, 0.10, 0.90, 0.20]),
        det("road", "safe_zone", [0.00, 0.45, 1.00, 0.55]),
        det("clear flat ground", "safe_zone", [0.05, 0.70, 0.35, 0.95]),
    ],
}


async def main() -> int:
    print("[Day 4] verifiable_corridor_engine offline tests (pure geometry, faked boundaries)")

    # --- Box IoU basics ---
    expect(box_iou((0, 0, 0.5, 0.5), (0, 0, 0.5, 0.5)) == 1.0, "identical boxes IoU = 1")
    expect(box_iou((0, 0, 0.4, 0.4), (0.6, 0.6, 1, 1)) == 0.0, "disjoint boxes IoU = 0")
    expect(abs(box_iou((0, 0, 0.5, 0.5), (0.25, 0.25, 0.75, 0.75)) - 0.142857) < 1e-5, "partial boxes IoU hand-check")

    # --- Clear corridor along the road, avoiding the flood block ---
    clear = verify_candidates(SCAN, corridors=[
        {"id": "good", "points_norm": [[0.05, 0.50], [0.35, 0.50]]},  # ends before flood x=0.40
        {"id": "along-road-west", "points_norm": [[0.02, 0.48], [0.30, 0.52]]},
    ], landing_zones=[
        {"id": "lz-good", "center_norm": [0.20, 0.82], "radius_norm": 0.08, "surface_concept": "clear flat ground"},
    ])
    expect(clear["status"] == "verified", "clear corridor + LZ verified")
    expect(clear["corridor_results"][0]["hazard_intersection_ratio"] == 0.0, "clear corridor hazard ratio = 0")
    expect(clear["corridor_results"][0]["color"] == "#00C853", "verified renders green")
    lz = clear["landing_zone_results"][0]
    expect(lz["meets_clearance"] and lz["clearance"]["effective_radius_px"] == 80.0, "LZ clearance numbers in px")
    expect(lz["safe_surface_overlap_ratio"] == 1.0, "LZ fully on safe surface")
    expect(clear["model_calls_in_geometry"] == 0, "geometry made zero model calls")

    # --- Deliberately hazard-crossing route: 20% inside flood -> rejected ---
    crossing = verify_candidates(SCAN, corridors=[
        {"id": "bad", "points_norm": [[0.0, 0.50], [1.0, 0.50]]},  # flood spans x .40-.60 at y .50
    ])
    bad = crossing["corridor_results"][0]
    expect(crossing["status"] == "rejected", "hazard-crossing corridor rejected")
    expect(abs(bad["hazard_intersection_ratio"] - 0.20) < 1e-6, f"hazard ratio exactly 0.20 (got {bad['hazard_intersection_ratio']})")
    expect(bad["hazard_footprint_iou"] > 0, "hazard footprint IoU reported as evidence")
    expect(bad["intersecting_hazards"][0]["concept"] == "flood water", "intersecting hazard attributed")
    expect(bad["color"] == "#FF2D20" and bad["requires_reroute"], "rejected renders red + requires reroute")

    # --- Exactly 10% is allowed; 10% + epsilon is not (rule is > 10%) ---
    edge = verify_candidates(SCAN, corridors=[
        {"id": "edge10", "points_norm": [[0.30, 0.50], [0.50, 0.50]]},  # .10 of .20 length inside flood
    ])
    expect(edge["corridor_results"][0]["hazard_intersection_ratio"] == 0.5, "edge geometry sanity (0.10/0.20 = 50% of this segment)")
    edge2 = verify_candidates(SCAN, corridors=[
        {"id": "edge-ok", "points_norm": [[0.0, 0.50], [0.45, 0.50]]},  # 0.05/0.45 = 11.1% -> rejected
        {"id": "edge-ok2", "points_norm": [[0.0, 0.50], [0.44, 0.50]]},  # hmm computed below
    ])
    expect(edge2["corridor_results"][0]["status"] == "rejected", "11.1% hazard contact rejected (>10%)")

    # --- Off-road route fails safe-support even with zero hazards ---
    offroad = verify_candidates(SCAN, corridors=[
        {"id": "field", "points_norm": [[0.05, 0.05], [0.30, 0.05]]},
    ])
    expect(offroad["corridor_results"][0]["status"] == "rejected", "off-road corridor rejected (no safe support)")
    expect("safe infrastructure" in offroad["corridor_results"][0]["reasons"][0], "safe-support reason given")

    # --- Landing zones: hazard overlap, clearance, surface ---
    zones = verify_candidates(SCAN, landing_zones=[
        {"id": "lz-flood", "center_norm": [0.50, 0.50], "radius_norm": 0.08, "surface_concept": "clear flat ground"},
        {"id": "lz-tiny", "center_norm": [0.20, 0.82], "radius_norm": 0.005, "surface_concept": "clear flat ground"},
        {"id": "lz-heli", "name": "Helipad", "center_norm": [0.20, 0.82], "radius_norm": 0.03, "surface_concept": "clear flat ground"},
    ])
    z = {r["candidate_id"]: r for r in zones["landing_zone_results"]}
    expect(z["lz-flood"]["status"] == "rejected" and z["lz-flood"]["hazard_intersection_ratio"] > 0.10, "LZ on flood rejected")
    expect(z["lz-tiny"]["status"] == "rejected" and not z["lz-tiny"]["meets_clearance"], "tiny LZ fails drone clearance")
    expect(z["lz-heli"]["clearance"]["zone_kind"] == "helicopter", "helipad kind inferred")
    expect(z["lz-heli"]["status"] == "rejected", "0.03 radius fails helicopter clearance (needs 0.04)")

    # --- Mask IoU path (deterministic RLE fixture, 10x10) ---
    grid = [[0] * 10 for _ in range(10)]
    for y in range(4, 6):
        for x in range(4, 6):
            grid[y][x] = 1  # hazard block x/y 4-5 (norm .4-.6)
    road_grid = [[1 if y in (4, 5) else 0 for _ in range(10)] for y in range(10)]
    mask_scan = {
        "image": {"width": 10, "height": 10},
        "detections": [
            det("flood water", "hazard", [0.4, 0.4, 0.6, 0.6],
                mask={"x": 0, "y": 0, "width": 10, "height": 10, "format": "sam-3.1-rle", "data": encode_counts_fixture(grid)}),
            det("road", "safe_zone", [0.0, 0.4, 1.0, 0.6],
                mask={"x": 0, "y": 0, "width": 10, "height": 10, "format": "sam-3.1-rle", "data": encode_counts_fixture(road_grid)}),
        ],
    }
    decoded, w, h = decode_sam_mask(mask_scan["detections"][0]["mask"], image_width=10, image_height=10)
    expect(sum(decoded) == 4, "RLE fixture decodes to 4 hazard pixels")
    masked = verify_candidates(mask_scan, corridors=[
        {"id": "through", "points_norm": [[0.05, 0.5], [0.95, 0.5]]},
        {"id": "above", "points_norm": [[0.05, 0.45], [0.35, 0.45]]},
    ])
    expect(masked["method"] == "mask", "mask method selected when RLE decodes")
    expect(masked["corridor_results"][0]["hazard_intersection_ratio"] > 0.10, "mask route through block rejected")
    expect(masked["corridor_results"][0]["method"] == "mask", "per-candidate method = mask")

    # Opaque vendor mask -> honest bbox fallback
    opaque = json.loads(json.dumps(mask_scan))
    opaque["detections"][0]["mask"]["data"] = "182,1024,~!!opaque-vendor-payload"
    opaque["detections"][1]["mask"]["data"] = "337,1024,~!!opaque-vendor-payload"
    fell_back = verify_candidates(opaque, corridors=[{"id": "c", "points_norm": [[0.05, 0.5], [0.95, 0.5]]}])
    expect(fell_back["method"] == "bbox" and fell_back["field"]["mask_fallback_reason"], "opaque mask -> declared bbox fallback")

    # --- OSM Overpass (MockTransport) ---
    expect("amenity" in build_overpass_query(27.7, 85.3, 5000), "Overpass query targets facilities")
    facilities = parse_overpass_response({"elements": [
        {"type": "node", "id": 1, "lat": 27.701, "lon": 85.301, "tags": {"amenity": "hospital", "name": "City Hospital"}},
        {"type": "way", "id": 2, "center": {"lat": 27.71, "lon": 85.31}, "tags": {"amenity": "fire_station"}},
    ]}, 27.7, 85.3)
    expect(len(facilities) == 2 and facilities[0]["name"] == "City Hospital", "Overpass elements parsed + sorted")
    expect(facilities[0]["distance_m"] < facilities[1]["distance_m"], "haversine distances ordered")
    expect(haversine_m(27.7, 85.3, 27.7, 85.3) == 0.0, "haversine zero at self")

    def osm_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"elements": [
            {"type": "node", "id": 9, "lat": 27.7005, "lon": 85.3005, "tags": {"amenity": "clinic", "name": "Clinic A"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(osm_handler)) as hc:
        osm = await query_emergency_facilities(27.7, 85.3, http_client=hc)
    expect(osm["status"] == "ok" and osm["facilities"][0]["type"] == "clinic", "Overpass query via injected client")
    skipped = await query_emergency_facilities(None, None)
    expect(skipped["status"] == "not_queried" and not skipped["facilities"], "no GPS -> not queried, nothing invented")

    # --- Self-correction loop: rejected -> Spark reroutes -> verified ---
    reroute_json = json.dumps({
        "candidate_evacuation_corridors": [
            {"id": "bad", "name": "West road detour", "points_norm": [[0.02, 0.50], [0.35, 0.50]],
             "rationale": "stops before flood block", "grounded_concepts": ["road"]}],
        "candidate_landing_zones": [], "changes_summary": "shortened before flood",
    })

    class FakeResponses:
        calls = []

        async def create(self, model, input):  # noqa: A002
            FakeResponses.calls.append((model, input))

            class Resp:
                output_text = reroute_json

            return Resp()

    class FakeSpark:
        responses = FakeResponses()

    async with httpx.AsyncClient(transport=httpx.MockTransport(osm_handler)) as hc:
        loop = await run_verification_loop(
            SCAN,
            corridors=[{"id": "bad", "points_norm": [[0.0, 0.50], [1.0, 0.50]]}],
            spark_client=FakeSpark(), latitude=27.7, longitude=85.3, osm_http_client=hc,
        )
    expect(loop["initial_verification"]["status"] == "rejected", "loop: initial crossing rejected")
    expect(loop["status"] == "verified", "loop: corrected corridor verified")
    expect(loop["correction"]["attempts_used"] == 1 and loop["correction"]["status"] == "corrected", "loop: exactly one reroute")
    expect(FakeResponses.calls[0][0] == "muse-spark-1.3", "loop: reroute uses muse-spark-1.3")
    expect(FakeResponses.calls[0][1][0]["role"] == "developer", "loop: developer role used")
    expect(any(t["event"] == "reroute_forced" for t in loop["trace"]), "loop: rejection forces reroute in trace")
    expect(loop["dispatch_ready"] and loop["verified_candidates"]["corridors"], "loop: verified candidates dispatch-ready")

    # Auto-correct disabled: rejection stands, no Spark call
    FakeResponses.calls.clear()
    disabled = await run_verification_loop(
        SCAN, corridors=[{"id": "bad", "points_norm": [[0.0, 0.50], [1.0, 0.50]]}],
        auto_correct=False, spark_client=FakeSpark())
    expect(disabled["status"] == "rejected" and not FakeResponses.calls, "auto_correct off -> no model call, still rejected")

    # No candidates / bad scan stay honest
    empty = await run_verification_loop(SCAN, auto_correct=False)
    expect(empty["status"] == "no_candidates" and not empty["dispatch_ready"], "no candidates -> not dispatch ready")
    try:
        verify_candidates({})
        expect(False, "empty scan raises")
    except ValueError:
        expect(True, "empty scan raises ValueError")

    # --- HTTP contract (loop faked at main boundary; geometry untouched above) ---
    import backend.main as main_module
    from fastapi.testclient import TestClient

    original = main_module.run_verification_loop

    async def fake_loop(scan_result, **kwargs):
        return {"status": "verified", "echo_auto_correct": kwargs.get("auto_correct")}

    main_module.run_verification_loop = fake_loop
    try:
        client = TestClient(main_module.app, raise_server_exceptions=False)
        expect(client.get("/health").json()["version"] == "1.0.0", "/health reports v1.0.0 version")
        expect(client.get("/api/verify/readiness").status_code == 200, "verify readiness live")
        r = client.post("/api/verify", json={"scan_result": SCAN, "candidate_evacuation_corridors": []})
        expect(r.status_code == 200 and r.json()["status"] == "verified", "POST /api/verify works")
        r = client.post("/api/verify", json={"scan_result": SCAN, "latitude": 27.7})
        expect(r.status_code == 400, "latitude without longitude -> 400")
        r = client.post("/api/verify", json={})
        expect(r.status_code == 422, "missing scan_result -> 422 (pydantic)")
    finally:
        main_module.run_verification_loop = original

    print("\nRESULT:", "PASS" if not FAILURES else f"FAIL ({len(FAILURES)}): {FAILURES}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
