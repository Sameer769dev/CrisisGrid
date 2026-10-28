"""Day 8 offline tests: preset catalogue integrity.
Run from repo root: python backend/test_presets.py
Checks metadata honesty, frontend asset existence, and frontend/backend
id parity. No network, no model calls: running a preset is a live-pipeline
action and is intentionally NOT exercised here.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.presets import PRESETS, get_preset, list_presets  # noqa: E402

passed = failed = 0
def expect(cond, label):
    global passed, failed
    if cond: passed += 1; print(f"  PASS {label}")
    else: failed += 1; print(f"  FAIL {label}")

def main():
    expect(len(PRESETS) == 3, "exactly 3 presets")
    ids = [p["id"] for p in PRESETS]
    expect(ids == ["urban-flood", "earthquake-bridge", "wildfire-helipad"], f"preset ids/order {ids}")
    payload = list_presets()
    expect(payload["model_calls"] == 0 and payload["count"] == 3, "catalogue is static metadata, zero model calls")
    expect("pre-baked" in payload["honesty_note"] or "nothing" in payload["honesty_note"].lower() or "produced live" in payload["honesty_note"], "honesty note declares live results")
    fe = (ROOT / "frontend" / "lib" / "presets.ts").read_text(encoding="utf-8")
    for preset in PRESETS:
        expect(preset["field_report"].strip() != "", f"{preset['id']} has a field report")
        expect(preset["expected_focus"], f"{preset['id']} declares expected focus concepts")
        expect("muse-image" in preset["image_provenance"] or "demo frame" in preset["image_provenance"].lower(), f"{preset['id']} declares image provenance")
        img = ROOT / "frontend" / "public" / preset["image_path"].lstrip("/")
        expect(img.exists() and img.stat().st_size > 10_000, f"{preset['id']} image asset exists ({img.name})")
        expect(f'id: "{preset["id"]}"' in fe, f"frontend fallback mirrors {preset['id']}")
        if preset["audio_path"]:
            audio = ROOT / "frontend" / "public" / preset["audio_path"].lstrip("/")
            expect(audio.exists() and audio.stat().st_size > 10_000, f"{preset['id']} radio WAV asset exists")
        expect(get_preset(preset["id"])["name"] == preset["name"], f"get_preset({preset['id']}) round-trips")
    expect(get_preset("nope") is None, "unknown preset returns None (404 upstream)")
    flood = get_preset("urban-flood")
    expect(flood["audio_path"] is not None, "flood preset carries the field-radio WAV")
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
