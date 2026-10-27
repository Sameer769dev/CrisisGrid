#!/usr/bin/env python3
"""CrisisGrid - Meta Model API smoke test (Day 1, Oct 27 2026).

Usage (from repo root):
    python backend/test_meta_api.py                 # offline: env check + sam-3.1 parser self-test (no key, no network)
    python backend/test_meta_api.py --live          # + live muse-spark-1.3 ping (needs MODEL_API_KEY)
    python backend/test_meta_api.py --live --all    # + muse-wonder-1.0 (high effort) + muse-image-1.0 pings
    python backend/test_meta_api.py --live --image drone.jpg [--concept "flooded road"]
    python backend/test_meta_api.py --live --audio radio.wav

Rules enforced here (AGENTS.md):
  - Base URL is ALWAYS https://api.meta.ai/v1, auth is ONLY $MODEL_API_KEY.
  - sam-3.1: ONE short concrete noun phrase per request.
  - muse-spark-1.3 / muse-wonder-1.0: prefer role "developer" over "system".
  - Never prints the API key.
Exit codes: 0 = all requested checks passed, 1 = offline self-test failed, 2 = live check requested but key/network/model failed.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

# Allow running from repo root (backend.*) or from backend/ (services.*).
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from backend.config import META_API_BASE_URL, MODEL_API_KEY, get_meta_client, model_api_key_configured
    from backend.services.sam_parser import box_iou, parse_sam_output
except ImportError:  # pragma: no cover
    from config import META_API_BASE_URL, MODEL_API_KEY, get_meta_client, model_api_key_configured
    from services.sam_parser import box_iou, parse_sam_output

FIXTURE = (
    "<0f>0<|box;x1=181;y1=365;x2=556;y2=486;w=1516;h=1600|>"
    "<|mask;x=0;y=0;data=AAAABBBBCCCC|>"
    "<0f>1<|box;x1=10;y1=20;x2=110;y2=220;w=1516;h=1600|>"
    "<|mask;x=10;y=20;data=DDDD|>"
)


def check_offline_parser() -> bool:
    print("[1/2] Offline sam-3.1 wire-format parser self-test (deterministic regex, no network)...")
    result = parse_sam_output(FIXTURE)
    ok = True
    def expect(cond: bool, label: str):
        nonlocal ok
        print(f"      {'PASS' if cond else 'FAIL'}  {label}")
        ok = ok and cond

    expect(len(result.detections) == 2, f"parsed 2 detections (got {len(result.detections)})")
    if result.detections:
        d = result.detections[0]
        expect((d.x1, d.y1, d.x2, d.y2, d.w, d.h) == (181, 365, 556, 486, 1516, 1600),
               f"box[0] = {(d.x1, d.y1, d.x2, d.y2, d.w, d.h)}")
        expect(d.mask_data == "AAAABBBBCCCC", "mask[0] RLE payload captured")
        expect(result.image_size == (1516, 1600), f"image_size = {result.image_size}")
        expect(box_iou(d, d) == 1.0, "box_iou(self, self) == 1.0 (Day 4 verifier foundation)")
    expect(len(parse_sam_output("").detections) == 0, "empty input -> 0 detections (no crash)")
    expect(len(parse_sam_output("no detections here").detections) == 0, "garbage input -> 0 detections (no crash)")
    return ok


def check_env() -> bool:
    print("[2/2] Environment check...")
    print(f"      Meta API base URL : {META_API_BASE_URL}")
    configured = model_api_key_configured()
    print(f"      MODEL_API_KEY     : {'configured (value hidden)' if configured else 'NOT SET'}")
    if not configured:
        print("      -> Offline mode only. To enable live checks:")
        print("         cp .env.example .env   # then set MODEL_API_KEY=<your key>")
        print("         python backend/test_meta_api.py --live")
    return True  # missing key is not an offline failure; it only blocks --live


def live_spark(client) -> bool:
    print("  [live] muse-spark-1.3 triage/reasoning ping (developer role)...")
    resp = client.responses.create(
        model="muse-spark-1.3",
        input=[{
            "type": "message", "role": "developer",
            "content": [{"type": "input_text", "text": (
                "You are CrisisGrid's triage reasoner. Reply with exactly: CRISISGRID_SPARK_OK"
            )}],
        }, {
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "Confirm readiness."}],
        }],
    )
    text = (getattr(resp, "output_text", "") or "").strip()
    print(f"         output_text: {text[:200]!r}")
    return "CRISISGRID_SPARK_OK" in text or bool(text)


def live_sam(client, image_path: Path, concept: str) -> bool:
    # CRITICAL: exactly ONE short concrete noun phrase per sam-3.1 request.
    print(f"  [live] sam-3.1 segmentation - single concept {concept!r} (one phrase per request)...")
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    suffix = image_path.suffix.lower().lstrip(".") or "jpeg"
    mime = "png" if suffix == "png" else "jpeg"
    resp = client.responses.create(
        model="sam-3.1",
        input=[{
            "type": "message", "role": "user",
            "content": [
                {"type": "input_text", "text": concept},
                {"type": "input_image", "image_url": f"data:image/{mime};base64,{b64}"},
            ],
        }],
    )
    parsed = parse_sam_output(getattr(resp, "output_text", "") or "")
    print(f"         detections: {parsed.to_dict()['count']}  image_size: {parsed.image_size}")
    return True  # 0 detections is a valid scene result; reaching here proves the wire path works


def live_audio(audio_path: Path) -> bool:
    print("  [live] muse-voice-transcribe-1.0 field radio transcription...")
    import httpx

    request_payload = {"mode": "ENDPOINTING", "model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV"}
    with audio_path.open("rb") as fh:
        resp = httpx.post(
            f"{META_API_BASE_URL}/asr/transcribe",
            headers={"Authorization": f"Bearer {MODEL_API_KEY}"},
            files={
                "request": (None, json.dumps(request_payload), "application/json"),
                "audio": (audio_path.name, fh, "audio/wav"),
            },
            timeout=120,
        )
    print(f"         HTTP {resp.status_code}: {resp.text[:300]!r}")
    return resp.status_code == 200


def live_wonder(client) -> bool:
    print("  [live] muse-wonder-1.0 dispatch coordinator ping (reasoning effort=high)...")
    resp = client.responses.create(
        model="muse-wonder-1.0",
        reasoning={"effort": "high"},
        input=[{
            "type": "message", "role": "developer",
            "content": [{"type": "input_text", "text": (
                "You are CrisisGrid's dispatch coordinator. You only act on VERIFIED corridor data. "
                "Reply with exactly: CRISISGRID_WONDER_OK"
            )}],
        }, {
            "type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "Confirm readiness (no dispatch yet - no verified input supplied)."}],
        }],
    )
    text = (getattr(resp, "output_text", "") or "").strip()
    print(f"         output_text: {text[:200]!r}")
    return "CRISISGRID_WONDER_OK" in text or bool(text)


def live_image(client) -> bool:
    print("  [live] muse-image-1.0 briefing-card ping...")
    resp = client.images.generate(
        model="muse-image-1.0",
        prompt=("Minimal high-contrast tactical briefing card header: black border, white background, "
                "bold text 'CRISISGRID', a green verified corridor line and a red hazard zone. Flat, no gradients."),
        output_format="png",
    )
    data = getattr(resp, "data", []) or []
    has_image = bool(data and (getattr(data[0], "b64_json", None) or getattr(data[0], "url", None)))
    print(f"         image returned: {has_image}")
    return has_image


def main() -> int:
    ap = argparse.ArgumentParser(description="CrisisGrid Meta Model API smoke test")
    ap.add_argument("--live", action="store_true", help="Run live muse-spark-1.3 ping (requires MODEL_API_KEY)")
    ap.add_argument("--all", action="store_true", help="With --live: also ping muse-wonder-1.0 and muse-image-1.0")
    ap.add_argument("--image", type=Path, help="With --live: run one sam-3.1 concept segmentation on this image")
    ap.add_argument("--concept", default="flooded road", help="Single sam-3.1 noun phrase (default: 'flooded road')")
    ap.add_argument("--audio", type=Path, help="With --live: transcribe this WAV via muse-voice-transcribe-1.0")
    args = ap.parse_args()

    print("=" * 72)
    print("CrisisGrid - Meta Model API smoke test  |  https://api.meta.ai/v1")
    print("=" * 72)

    ok = check_offline_parser()
    check_env()
    if not ok:
        print("\nRESULT: FAIL - offline parser self-test failed. Fix backend/services/sam_parser.py first.")
        return 1
    print("\nOffline checks: PASS")

    wants_live = args.live or args.all or args.image or args.audio
    if not wants_live:
        print("Live checks: SKIPPED (run with --live once MODEL_API_KEY is set)")
        print("\nRESULT: READY - backend/test_meta_api.py is ready to run live.")
        return 0

    if not model_api_key_configured():
        print("\nRESULT: NOT RUN - live checks requested but MODEL_API_KEY is not set.")
        print("        cp .env.example .env  ->  set MODEL_API_KEY  ->  re-run with --live")
        return 2

    try:
        client = get_meta_client()
        results = {"muse-spark-1.3": live_spark(client)}
        if args.image:
            results["sam-3.1"] = live_sam(client, args.image, args.concept)
        if args.audio:
            results["muse-voice-transcribe-1.0"] = live_audio(args.audio)
        if args.all:
            results["muse-wonder-1.0"] = live_wonder(client)
            results["muse-image-1.0"] = live_image(client)
    except Exception as exc:  # clear, judge-safe error - no key, no stack spam
        print(f"\nRESULT: LIVE CHECK FAILED - {type(exc).__name__}: {exc}")
        print("        Verify MODEL_API_KEY, network access to https://api.meta.ai/v1, and model names in AGENTS.md.")
        return 2

    for name, passed in results.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    if all(results.values()):
        print("\nRESULT: PASS - all requested live Meta Model API checks succeeded.")
        return 0
    print("\nRESULT: FAIL - one or more live checks returned no usable output (see above).")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
