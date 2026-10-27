"""Offline tests for Day 3 voice transcription + Spark triage.

Run:  python backend/test_voice_and_triage.py   (no key, no network)

Covers: WAV contract validation, ASR multipart shape via httpx MockTransport,
transcript extraction, deterministic scan summarisation (masks stripped),
Spark JSON parsing/validation, candidate normalisation (always unverified),
text fallback, and the /api/triage HTTP contract with the Spark call faked.
"""
import asyncio
import io
import json
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from backend.services.voice_and_triage import (
    extract_transcript,
    parse_spark_triage,
    probe_wav_format,
    run_triage,
    summarize_scan,
    transcribe_audio,
    validate_wav_for_asr,
    TriageParseError,
)

FAILURES = []


def expect(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILURES.append(label)


def make_wav(sample_rate=16000, channels=1, sampwidth=2, seconds=0.1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sampwidth)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * int(sample_rate * seconds) * channels)
    return buf.getvalue()


SPARK_JSON = json.dumps({
    "incident_type": "urban flood",
    "severity": "HIGH",
    "urgency_score": 140,
    "summary": "Road flooded; three people stranded in a vehicle near the bridge.",
    "people_at_risk": {"count_estimate": 3, "description": "stranded vehicle occupants", "confidence": 0.8},
    "hazards_identified": ["flood water"],
    "passable_infrastructure": ["road"],
    "blocked_infrastructure": ["road segment near bridge"],
    "priorities": [
        {"rank": 2, "category": "Evacuation", "action": "Open evacuation corridor", "rationale": "r2", "target_concepts": ["road"], "location_hint": None},
        {"rank": 1, "category": "Medical", "action": "Dispatch medical rescue to stranded vehicle", "rationale": "r1", "target_concepts": ["stranded vehicle"], "location_hint": "near bridge"},
    ],
    "candidate_evacuation_corridors": [
        {"id": "", "name": "Road corridor", "purpose": "evacuation", "points_norm": [[0.1, 0.9], [0.5, 0.6], [0.9, 0.55]], "start_label": "south", "end_label": "bridge", "rationale": "follows road", "grounded_concepts": ["road"]},
        {"id": "bad", "name": "single point", "points_norm": [[0.5, 0.5]], "rationale": "invalid"},
    ],
    "candidate_landing_zones": [
        {"id": "", "name": "Flat ground LZ", "center_norm": [0.7, 0.3], "radius_norm": 0.07, "surface_concept": "clear flat ground", "rationale": "flat", "grounded_concepts": ["clear flat ground"]}
    ],
    "recommended_units": ["medical team", {"unit_type": "boat rescue", "task": "extract occupants", "priority_rank": 1}],
    "missing_information": ["water depth"],
    "assumptions": [],
    "confidence": 0.75,
})

SCAN = {
    "status": "ok", "model": "sam-3.1", "verification_status": "unverified_segmentation_only",
    "image": {"width": 1280, "height": 853},
    "summary": {"total_detections": 2, "total_masks": 2, "hazards": {}, "safe_zones": {}},
    "concept_layers": [
        {"concept": "flood water", "kind": "hazard", "status": "ok", "detection_count": 1, "mask_count": 1,
         "detections": [{"bbox_xyxy_norm": [0.0, 0.56, 1.0, 0.83], "area_fraction": 0.26, "mask": {"data": "SECRET-MASK"}}]},
        {"concept": "road", "kind": "safe_zone", "status": "ok", "detection_count": 1, "mask_count": 1,
         "detections": [{"bbox_xyxy_norm": [0.0, 0.5, 1.0, 1.0], "area_fraction": 0.49, "mask": {"data": "SECRET-MASK"}}]},
    ],
    "detections": [],
}


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    async def create(self, model, input):  # noqa: A002 - mirrors SDK kwarg
        self.calls.append({"model": model, "input": input})

        class Resp:
            pass

        resp = Resp()
        resp.output_text = self.output_text
        return resp


class FakeSparkClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(output_text)


async def main() -> int:
    print("[Day 3] voice_and_triage offline tests (fake ASR transport + fake Spark, no network)")

    # --- WAV contract ---
    info = probe_wav_format(make_wav())
    expect(info["sample_rate_hz"] == 16000 and info["channels"] == 1, "probes valid 16kHz mono WAV")
    expect(validate_wav_for_asr(make_wav(24000))["sample_rate_hz"] == 24000, "24kHz WAV accepted")
    for bad, label in [(make_wav(22050), "22.05kHz rejected"), (make_wav(channels=2), "stereo rejected"), (b"not wav", "non-WAV rejected")]:
        try:
            validate_wav_for_asr(bad)
            expect(False, label)
        except ValueError:
            expect(True, label)

    # --- Transcript extraction ---
    expect(extract_transcript({"transcript": " hello "}) == "hello", "extracts transcript key")
    expect(extract_transcript({"segments": [{"text": "a"}, {"text": "b"}]}) == "a b", "joins segment text")
    expect(extract_transcript({"nope": 1}) == "", "unknown shape -> empty (no fabrication)")

    # --- ASR multipart shape (MockTransport, dummy key only) ---
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["content_type"] = request.headers.get("content-type", "")
        captured["body"] = request.content
        return httpx.Response(200, json={"sessionId": "s1", "transcript": "Mayday road flooded", "audioDurationMs": 1000})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        asr = await transcribe_audio(make_wav(), filename="radio.wav", api_key="test-key", http_client=http_client)
    expect(asr["transcript"] == "Mayday road flooded", "ASR transcript returned")
    expect(captured["url"].endswith("/asr/transcribe"), "ASR posts to /asr/transcribe on Meta base URL")
    expect(captured["auth"] == "Bearer test-key", "ASR sends single MODEL_API_KEY bearer (dummy in test)")
    body = captured["body"].decode("utf-8", "ignore")
    expect('"mode": "ENDPOINTING"' in body or '"mode":"ENDPOINTING"' in body.replace(" ", ""), "multipart request part carries ENDPOINTING mode")
    expect("muse-voice-transcribe-1.0" in body and "field-radio" not in body, "multipart carries model name (filename radio.wav sent separately)")
    expect("audio/wav" in captured["content_type"] or "multipart/form-data" in captured["content_type"], "multipart form-data used")

    # ASR HTTP failure surfaces honestly
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"error": {"message": "bad wav"}}))) as hc:
        try:
            await transcribe_audio(make_wav(), api_key="test-key", http_client=hc)
            expect(False, "ASR 400 raises")
        except RuntimeError as exc:
            expect("400" in str(exc), "ASR 400 raises TranscriptionError with status")

    # --- Scan summary strips masks ---
    summary = summarize_scan(SCAN, scan_id="scan-1")
    expect(summary["provided"] and summary["scan_id"] == "scan-1", "scan summary carries scan_id")
    expect("SECRET-MASK" not in json.dumps(summary), "RLE mask payloads stripped before Spark")
    expect(set(summary["concepts_with_detections"]) == {"flood water", "road"}, "grounded concepts listed")

    # --- Spark parsing / normalisation ---
    triage = parse_spark_triage("```json\n" + SPARK_JSON + "\n```")
    expect(triage.severity == "high" and triage.urgency_score == 100, "severity normalised, urgency clamped to 100")
    try:
        parse_spark_triage("not json at all")
        expect(False, "garbage Spark output raises")
    except TriageParseError:
        expect(True, "garbage Spark output raises TriageParseError (never fabricated)")

    # --- Full run: text fallback + fake Spark ---
    fake = FakeSparkClient(SPARK_JSON)
    result = await run_triage(
        text="Three people stranded in a vehicle, road flooded near bridge.",
        scan_result=SCAN, scan_id="scan-1", spark_client=fake,
    )
    call = fake.responses.calls[0]
    expect(call["model"] == "muse-spark-1.3", "triage uses muse-spark-1.3")
    expect(call["input"][0]["role"] == "developer", "developer role preferred over system")
    prompt_text = call["input"][1]["content"][0]["text"]
    expect("SECRET-MASK" not in prompt_text, "Spark prompt contains no mask payloads")
    expect(result["input"]["source"] == "text_fallback", "text fallback source recorded")
    expect(result["triage"]["priorities"][0]["rank"] == 1 and "medical" in result["triage"]["priorities"][0]["category"], "priorities re-ranked deterministically")
    corridors = result["candidate_evacuation_corridors"]
    expect(len(corridors) == 1 and corridors[0]["status"] == "unverified_candidate", "single-point corridor dropped; rest unverified")
    expect(corridors[0]["points_norm"][0] == {"x": 0.1, "y": 0.9}, "corridor coords normalized [x,y] -> {x,y}")
    zones = result["candidate_landing_zones"]
    expect(len(zones) == 1 and zones[0]["center_norm"] == {"x": 0.7, "y": 0.3}, "landing zone centre normalized")
    expect(result["verification_status"] == "unverified_triage_proposal", "never claims verified safety")
    expect(any(t["event"] == "candidates_marked_unverified" for t in result["trace"]), "trace marks candidates unverified for Day 4")

    # --- Full run: audio path uses ASR transcript ---
    async with httpx.AsyncClient(transport=transport) as http_client:
        result2 = await run_triage(
            audio_bytes=make_wav(), audio_filename="radio.wav",
            spark_client=FakeSparkClient(SPARK_JSON), asr_http_client=http_client, api_key="test-key",
        )
    expect(result2["input"]["source"] == "audio_transcription", "audio path source = transcription")
    expect(result2["transcript"] == "Mayday road flooded", "ASR transcript feeds Spark")

    # --- HTTP contract (Spark faked at main-module boundary) ---
    import backend.main as main_module
    from fastapi.testclient import TestClient

    original = main_module.run_triage

    async def fake_run_triage(**kwargs):
        return {"status": "ok", "echo_text": kwargs.get("text"), "echo_audio": bool(kwargs.get("audio_bytes"))}

    main_module.run_triage = fake_run_triage
    try:
        client = TestClient(main_module.app, raise_server_exceptions=False)
        expect(str(client.get("/health").json()["version"]).startswith("0."), "/health responds with a version")
        expect(client.get("/api/triage/readiness").status_code == 200, "triage readiness endpoint live")
        r = client.post("/api/triage/text", json={"text": "typed report", "scan_id": "s9"})
        expect(r.status_code == 200 and r.json()["echo_text"] == "typed report", "POST /api/triage/text works")
        r = client.post("/api/triage", data={"text": "typed via form"})
        expect(r.status_code == 200, "POST /api/triage multipart text fallback works")
        r = client.post("/api/triage", data={})
        expect(r.status_code == 400, "missing audio+text -> 400")
        r = client.post("/api/triage", data={"text": "x", "scan_json": "{bad json"})
        expect(r.status_code == 400, "invalid scan_json -> 400")
    finally:
        main_module.run_triage = original

    print("\nRESULT:", "PASS" if not FAILURES else f"FAIL ({len(FAILURES)}): {FAILURES}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
