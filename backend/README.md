# CrisisGrid Backend (FastAPI + Deterministic Geometry Verifier)

**100% Official Meta Model API (`https://api.meta.ai/v1`)** authenticated via a single `MODEL_API_KEY` environment variable, paired with pure local Python geometric verification (`verifiable_corridor_engine.py`) and free **OpenStreetMap Overpass API** emergency facility lookups.

See [`../AGENTS.md`](../AGENTS.md) for binding architectural rules and [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for mathematical proofs and wire protocols.

---

## ⚡ Quick Start

```bash
# From repository root:
cp .env.example .env          # Set MODEL_API_KEY=<your_meta_api_key>
pip install -r backend/requirements.txt

# Launch the FastAPI server (http://localhost:8000 | Swagger UI: http://localhost:8000/docs)
uvicorn backend.main:app --reload --port 8000
```

---

## 🧪 Offline Verification & Live Smoke Test Suite

All 7 offline test suites (**215/215 assertions**) execute in **seconds with no API key and no network access**. External boundaries (`api.meta.ai/v1` and `overpass-api.de`) are isolated via dependency injection and `httpx.MockTransport`, while all regex parsing, WAV header validation, RLE mask decoding, and bounding-box/polyline geometry run for real:

```bash
# 1. Day 1: sam-3.1 wire-format regex parser & box IoU self-test + env check (7 assertions)
python backend/test_meta_api.py

# 2. Day 2: Parallel sam-3.1 9-concept scanner contract & failure isolation (18 assertions)
python backend/test_sam_hazard_scanner.py

# 3. Day 3: WAV header validator, ASR multipart contract & muse-spark-1.3 triage (38 assertions)
python backend/test_voice_and_triage.py

# 4. Day 4: Deterministic geometry verifier, RLE mask IoU, OSM Overpass & Spark re-route loop (48 assertions)
python backend/test_verifiable_corridor_engine.py

# 5. Day 5: Verified-only dispatch gate, Wonder JSON contract, deterministic guardrail,
#    briefing-card facts-only prompt & unified pipeline at faked boundaries (55 assertions)
python backend/test_wonder_commander.py

# 6. Day 7: Before/after greedy IoU damage delta, post-clearance re-verification & sector ranking (24 assertions)
python backend/test_damage_delta.py

# 7. Day 8: Global disaster preset catalogue, asset existence & provenance checks (25 assertions)
python backend/test_presets.py
```

### Optional Live Meta Model API Checks (`--live`, requires `MODEL_API_KEY`)

```bash
python backend/test_meta_api.py --live                                          # muse-spark-1.3 ping
python backend/test_meta_api.py --live --image live-flood.jpg                   # sam-3.1 single-concept segmentation
python backend/test_meta_api.py --live --audio radio-report.wav                 # muse-voice-transcribe-1.0 ASR
python backend/test_meta_api.py --live --all                                    # spark + wonder (high effort) + image pings
```

---

## 🔌 FastAPI Endpoints (`backend/main.py`)

| Method | Path | Day | Status | Contract Summary |
| :---: | :--- | :---: | :---: | :--- |
| `GET` | `/health` | 1 | **Live** | Service version, model map, and `model_api_key_configured` boolean (never exposes key). |
| `GET` | `/api/config/status` | 1 | **Live** | Frontend-safe configuration status and setup hint. |
| `POST` | `/api/sam/parse` | 1 | **Live** | Offline deterministic regex parser for `sam-3.1` `<\|box;...\|><\|mask;...\|>` wire format. |
| `GET` | `/api/scan-hazards/concepts` | 2 | **Live** | Canonical 5-hazard (`#FF2D20`) and 4-safe-zone (`#00C853`) concept vocabularies. |
| `POST` | `/api/scan-hazards` *(alias `/api/scan`)* | 2 | **Live** | Multipart `file` (JPEG/PNG/WebP $\le 15\text{ MB}$), optional `concepts` override. Fans out 1 async `sam-3.1` request per concept. |
| `GET` | `/api/triage/readiness` | 3 | **Live** | Reports WAV audio requirements (`16000`/`24000` Hz mono `s16le`), text fallback, and grounding fields. |
| `POST` | `/api/triage` | 3 | **Live** | Multipart `audio` (WAV $\le 25\text{ MB}$) and/or `text`, optional `scan_json`, `scan_id`, `image`. Runs `muse-voice-transcribe-1.0` + `muse-spark-1.3`. |
| `POST` | `/api/triage/text` | 3 | **Live** | JSON text-fallback variant (`{text, scan_result, scan_id}`) for browser clients without audio. |
| `GET` | `/api/verify/readiness` | 4 | **Live** | Reports deterministic verifier rules ($\le 10\%$ hazard contact, $\ge 50\%$ safe support) and Overpass config. |
| `POST` | `/api/verify` | 4 | **Live** | Deterministic Python verification (`verifiable_corridor_engine.py`) + OSM Overpass lookup + bounded `muse-spark-1.3` re-route loop. |
| `GET` | `/api/dispatch/readiness` | 5 | **Live** | Day 5 trust contract: verified-only input, deterministic guardrail, facts-only briefing card. |
| `POST` | `/api/dispatch` | 5 | **Live** | JSON `{verification_result, triage_result, include_briefing_card}`. Deterministic re-gate -> `muse-wonder-1.0` (`reasoning={"effort": "high"}`) multi-unit protocol -> guardrail holds units aimed at unverified targets -> `muse-image-1.0` PNG briefing card (base64). `422` when nothing is verified. |
| `POST` | `/api/run-crisisgrid` | 5 | **Live** | Unified pipeline in one multipart call: `image` + `audio` (WAV) and/or `text`, optional `latitude`/`longitude`, `auto_correct`, `include_briefing_card`, `concepts`. Runs Day 2 scan -> Day 3 triage -> Day 4 verify -> Day 5 dispatch with a concatenated agent trace; dispatch is skipped honestly when no candidate verifies. |
| `POST` | `/api/delta` | 7 | **Live** | JSON `{scan_before, scan_after, iou_threshold}`. Deterministic greedy per-concept IoU box matching (persistent/new/cleared), render-mapped delta detections for the canvas, worsened/improved/stable verdict. Zero model calls; never verifies a route. |
| `POST` | `/api/delta/verify-clearance` | 7 | **Live** | JSON `{scan_after, triage_result|candidates, verification_before}`. Re-runs the Day 4 verifier on the AFTER scan only (no Spark re-route); reports per-candidate blocked->verified flips and returns a Day 5-ready `verification_result`. |
| `POST` | `/api/sectors/rank` | 7 | **Live** | JSON `{sectors:[snapshots]}`. Published deterministic 0-100 ranking (urgency/severity/people/hazard/access) with breakdowns and recommended actions. Ranking never verifies a route. |
| `GET` | `/api/delta/readiness` | 7 | **Live** | Day 7 trust contract: delta highlights change; only the Day 4 verifier flips candidate status. |
| `GET` | `/api/presets` (+ `/api/presets/{id}`) | 8 | **Live** | Static honest preset catalogue (imagery/report metadata, declared provenance, zero model calls, no pre-baked results). Running a preset executes the full live pipeline. |

---

## 🧩 Service Architecture (`backend/services/`)

- **[`sam_parser.py`](./services/sam_parser.py):** Pure deterministic regex parser (`parse_sam_output`) and pixel bounding-box IoU helper (`box_iou`). Zero model calls.
- **[`sam_hazard_scanner.py`](./services/sam_hazard_scanner.py):** Enforces the `sam-3.1` one-noun-phrase-per-request rule, runs parallel `asyncio.gather` across all 9 concepts, normalizes coordinates, and isolates per-concept errors.
- **[`voice_and_triage.py`](./services/voice_and_triage.py):** Validates WAV headers locally (`probe_wav_format`, `validate_wav_for_asr`), calls `muse-voice-transcribe-1.0` (`ENDPOINTING`), strips RLE masks from `sam-3.1` scans (`summarize_scan`), and calls `muse-spark-1.3` (`role="developer"`) to produce ranked priorities and `unverified_candidate` corridors/LZs.
- **[`verifiable_corridor_engine.py`](./services/verifiable_corridor_engine.py):** Pure local Python geometry engine (`verify_candidates`) supporting RLE mask decoding and exact Liang-Barsky segment-box clipping, OpenStreetMap Overpass facility lookup (`query_emergency_facilities`), and bounded `muse-spark-1.3` self-correction (`run_verification_loop`).
- **[`presets.py`](./services/presets.py):** Day 8 preset catalogue - three global disaster presets (urban flood, earthquake bridge/rubble, wildfire helipad) with imagery paths, field reports, expected-focus concepts and declared image provenance. Inputs only; every result is produced live.
- **[`damage_delta.py`](./services/damage_delta.py):** Day 7 deterministic change engine. `compute_damage_delta` matches before/after Day 2 detections per concept by greedy box IoU; `verify_clearance` re-runs the Day 4 verifier on the post-clearance scan so a corridor flips blocked -> verified only on new geometric evidence; `rank_sectors` applies the published multi-sector priority formula. Zero model calls throughout.
- **[`wonder_commander.py`](./services/wonder_commander.py):** Day 5 dispatch commander. `extract_dispatchable_state` re-gates every Day 4 candidate in pure Python (verification record + hazard ratio <= 10%) so only verified corridors/zones reach `muse-wonder-1.0` (`reasoning={"effort": "high"}`); `sanitize_dispatch_plan` then holds any unit aimed at an unverified target. `muse-image-1.0` briefing cards are prompted from verified facts only, and `run_crisisgrid_pipeline` chains Days 2-5 behind `POST /api/run-crisisgrid`.
