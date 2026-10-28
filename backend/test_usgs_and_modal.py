"""Offline tests for Live USGS Seismic Telemetry & Modal Serverless Configuration.

Run from repo root:  python backend/test_usgs_and_modal.py
No network, no MODEL_API_KEY: USGS HTTP calls are faked with httpx.MockTransport.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.modal_app import MODAL_CONFIG, detect_compute_runtime  # noqa: E402
from backend.services.usgs_feed import (  # noqa: E402
    USGS_FEEDS,
    UsgsUpstreamError,
    fetch_usgs_live_events,
    normalize_usgs_feature,
)

passed = failed = 0


def expect(cond: bool, label: str) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")


SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "metadata": {"title": "USGS Magnitude 4.5+ Earthquakes, Past Day", "status": 200, "count": 3},
    "features": [
        {
            "type": "Feature",
            "id": "us7000test1",
            "properties": {
                "mag": 6.8,
                "place": "22 km SSW of Marrakech, Morocco",
                "time": 1730000000000,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000test1",
                "felt": 412,
                "mmi": 7.4,
                "alert": "red",
                "tsunami": 0,
                "title": "M 6.8 - 22 km SSW of Marrakech, Morocco",
            },
            "geometry": {"type": "Point", "coordinates": [-8.0083, 31.4295, 18.5]},
        },
        {
            "type": "Feature",
            "id": "us7000test2",
            "properties": {
                "mag": 5.6,
                "place": "35 km E of Hualien City, Taiwan",
                "time": 1730003600000,
                "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000test2",
                "felt": 95,
                "mmi": 5.8,
                "alert": "yellow",
                "tsunami": 1,
                "title": "M 5.6 - 35 km E of Hualien City, Taiwan",
            },
            "geometry": {"type": "Point", "coordinates": [121.9512, 23.9769, 12.1]},
        },
        {
            "type": "Feature",
            "id": "us7000test3",
            "properties": {
                "mag": 4.2,
                "place": "10 km N of Ridgecrest, CA",
                "time": 1730007200000,
                "alert": "green",
                "tsunami": 0,
            },
            "geometry": {"type": "Point", "coordinates": [-117.67, 35.71, 6.4]},
        },
    ],
}


async def main() -> int:
    print("== USGS feature normalization & deterministic severity ==")
    ev1 = normalize_usgs_feature(SAMPLE_GEOJSON["features"][0])
    expect(ev1 is not None and ev1["event_id"] == "us7000test1", "normalizes USGS feature ID")
    expect(ev1["latitude"] == 31.4295 and ev1["longitude"] == -8.0083 and ev1["depth_km"] == 18.5, "extracts [lon, lat, depth] -> lat/lon/depth_km")
    expect(ev1["severity_estimate"] == "critical" and ev1["urgency_estimate"] >= 80, "M6.8 red alert classified critical")
    expect("M6.8" in ev1["field_report"] and "Marrakech" in ev1["field_report"], "telemetry field report cites magnitude and place")

    ev2 = normalize_usgs_feature(SAMPLE_GEOJSON["features"][1])
    expect(ev2["tsunami_warning"] is True and "TSUNAMI" in ev2["field_report"], "tsunami=1 sets tsunami_warning and advisory note")
    expect(normalize_usgs_feature({"properties": {}, "geometry": {"coordinates": [999, 999]}}) is None, "out-of-range coordinates rejected")
    expect(normalize_usgs_feature("not-a-dict") is None, "non-dict feature rejected")

    print("== USGS live feed fetch via MockTransport (zero network) ==")
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=SAMPLE_GEOJSON))
    async with httpx.AsyncClient(transport=transport) as client:
        res = await fetch_usgs_live_events(feed="4.5_day", min_magnitude=4.5, limit=5, http_client=client)
    expect(res["status"] == "ok" and res["model_calls"] == 0, "USGS fetch makes zero AI model calls")
    expect(res["count"] == 2 and res["total_matching"] == 2, "filters out M4.2 below min_magnitude=4.5")
    expect(res["events"][0]["event_id"] == "us7000test1" and res["events"][1]["event_id"] == "us7000test2", "sorted by magnitude descending")
    expect(any(t["step"] == "usgs" and t["event"] == "seismic_feed_loaded" for t in res["trace"]), "emits verifiable trace entry")

    err_transport = httpx.MockTransport(lambda req: httpx.Response(503, text="Service Unavailable"))
    async with httpx.AsyncClient(transport=err_transport) as err_client:
        try:
            await fetch_usgs_live_events(http_client=err_client)
            expect(False, "HTTP 503 raises UsgsUpstreamError")
        except UsgsUpstreamError as exc:
            expect(exc.status_code == 503, "HTTP 503 raises UsgsUpstreamError with status_code=503")

    try:
        await fetch_usgs_live_events(feed="invalid_feed")
        expect(False, "invalid feed name raises ValueError")
    except ValueError:
        expect(True, "invalid feed name raises ValueError")

    print("== Modal serverless CPU runtime configuration (AGENTS.md §2 compliance) ==")
    expect(MODAL_CONFIG["gpu"] is None, "Modal config requests zero third-party GPUs (AGENTS.md §2)")
    expect(MODAL_CONFIG["ai_inference_provider"] == "https://api.meta.ai/v1", "AI inference strictly pinned to https://api.meta.ai/v1")
    expect(MODAL_CONFIG["min_containers"] >= 1 and MODAL_CONFIG["cpu_cores"] >= 4.0, "always-warm 4-vCPU container configured")
    prev_env = os.environ.get("CRISISGRID_RUNTIME")
    try:
        os.environ["CRISISGRID_RUNTIME"] = "modal"
        expect(detect_compute_runtime() == "modal_serverless_cpu", "detects modal_serverless_cpu runtime")
    finally:
        if prev_env is None:
            os.environ.pop("CRISISGRID_RUNTIME", None)
        else:
            os.environ["CRISISGRID_RUNTIME"] = prev_env

    print("== FastAPI HTTP contract (/api/usgs/* & /api/runtime/modal) ==")
    import backend.main as main_module
    from fastapi.testclient import TestClient

    orig_fetch = main_module.fetch_usgs_live_events

    async def fake_fetch_usgs(**kwargs):
        async with httpx.AsyncClient(transport=transport) as c:
            return await orig_fetch(http_client=c, **kwargs)

    main_module.fetch_usgs_live_events = fake_fetch_usgs
    try:
        tc = TestClient(main_module.app, raise_server_exceptions=False)
        h = tc.get("/health").json()
        expect("compute_runtime" in h and h["version"] == "1.0.0", "/health includes compute_runtime and v1.0.0")
        r_ready = tc.get("/api/usgs/readiness")
        expect(r_ready.status_code == 200 and set(USGS_FEEDS).issubset(set(r_ready.json()["feeds"])), "GET /api/usgs/readiness lists USGS feeds")
        r_live = tc.get("/api/usgs/live?feed=4.5_day&min_magnitude=4.5&limit=2")
        expect(r_live.status_code == 200 and len(r_live.json()["events"]) == 2, "GET /api/usgs/live returns normalized events")
        r_modal = tc.get("/api/runtime/modal")
        expect(r_modal.status_code == 200 and r_modal.json()["modal_config"]["gpu"] is None, "GET /api/runtime/modal exposes compliant Modal profile")
    finally:
        main_module.fetch_usgs_live_events = orig_fetch

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
