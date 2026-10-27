"""Offline tests for the Day 2 parallel sam-3.1 hazard scanner.

Run:  python backend/test_sam_hazard_scanner.py   (no key, no network)

Uses an injected fake async client - the production scanner accepts a client
purely so this contract (one noun phrase per request, parallel fan-out,
normalized geometry, per-concept failure isolation) stays testable offline.
"""
import asyncio
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from backend.services.sam_hazard_scanner import (
    DEFAULT_CONCEPTS,
    HAZARD_CONCEPTS,
    SAFE_ZONE_CONCEPTS,
    scan_hazards,
    validate_concepts,
)

WIRE = (
    "<0f>0<|box;x1=181;y1=365;x2=556;y2=486;w=1516;h=1600|>"
    "<|mask;x=0;y=0;data=rle-payload|>"
)


class FakeResponses:
    def __init__(self, fail_concept=None, delay=0.05):
        self.calls = []
        self.fail_concept = fail_concept
        self.delay = delay

    async def create(self, model, input):  # noqa: A002 - mirrors SDK kwarg
        concept = input[0]["content"][0]["text"]
        self.calls.append((model, concept))
        await asyncio.sleep(self.delay)
        if concept == self.fail_concept:
            raise RuntimeError("simulated concept failure")
        text = WIRE if concept in ("road", "flood water") else ""

        class Resp:
            output_text = text

        return Resp()


class FakeClient:
    def __init__(self, **kw):
        self.responses = FakeResponses(**kw)


def make_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 120, 120)).save(buf, "JPEG")
    return buf.getvalue()


async def main() -> int:
    failures = []

    def expect(cond, label):
        print(("  PASS  " if cond else "  FAIL  ") + label)
        if not cond:
            failures.append(label)

    print("[Day 2] sam_hazard_scanner offline contract tests (fake async client, no network)")

    expect(set(DEFAULT_CONCEPTS) == set(HAZARD_CONCEPTS) | set(SAFE_ZONE_CONCEPTS), "default concepts = hazards + safe zones")
    expect(len(DEFAULT_CONCEPTS) == 9, "9 canonical concepts")

    # Parallel fan-out, one phrase per request
    client = FakeClient()
    started = time.perf_counter()
    result = await scan_hazards(make_jpeg(), media_type="image/jpeg", filename="t.jpg", client=client)
    elapsed = time.perf_counter() - started
    expect(len(client.responses.calls) == 9, f"9 sam-3.1 calls issued (got {len(client.responses.calls)})")
    expect(all(m == "sam-3.1" for m, _ in client.responses.calls), "all calls use sam-3.1")
    expect({c for _, c in client.responses.calls} == set(DEFAULT_CONCEPTS), "exactly one noun phrase per request")
    expect(elapsed < 0.35, f"requests ran in parallel ({elapsed:.2f}s, not ~0.45s serial)")

    # Normalized geometry + masks
    expect(result["status"] == "ok", "status ok when all concepts succeed")
    expect(result["summary"]["total_detections"] == 2, "road + flood water detections parsed")
    road = next(d for d in result["detections"] if d["concept"] == "road")
    expect(road["kind"] == "safe_zone" and road["color"] == "#00C853", "road is green safe zone")
    expect(abs(road["bbox"]["x_min"] - 181 / 1516) < 1e-5, "bbox normalized with SAM-declared w/h")
    expect(road["has_mask"] and road["mask"]["format"] == "sam-3.1-rle", "RLE mask captured")
    flood = next(d for d in result["detections"] if d["concept"] == "flood water")
    expect(flood["kind"] == "hazard" and flood["color"] == "#FF2D20", "flood water is red hazard")
    expect(result["verification_status"] == "unverified_segmentation_only", "never claims verified safety")

    # Failure isolation
    result2 = await scan_hazards(make_jpeg(), client=FakeClient(fail_concept="debris"))
    expect(result2["status"] == "partial", "one failed concept -> partial, scan survives")
    expect(result2["summary"]["concepts_failed"] == 1, "failure counted in summary")

    # Validation guards
    for bad in (b"", b"not an image"):
        try:
            await scan_hazards(bad, client=FakeClient())
            expect(False, f"rejects {bad[:8]!r}")
        except ValueError:
            expect(True, f"rejects invalid image {bad[:8]!r}")
    try:
        validate_concepts(["road, bridge"])
        expect(False, "rejects multi-concept phrase")
    except ValueError:
        expect(True, "rejects multi-concept phrase (one phrase per request rule)")

    print("\nRESULT:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
