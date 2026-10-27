# CrisisGrid — Agent Instructions & Architecture

> **Hackathon:** Meta Global AI Developer Hackathon — "Push the Frontier" (Oct 26 – Nov 4, 2026)
> **Project:** CrisisGrid — Autonomous Multimodal Disaster Triage, Infrastructure Assessment & Emergency Dispatch Agent
> **This file is binding for all agents and contributors working in this repo.** Read it before writing any code.

## 1. Global Vision

When natural disasters (floods, earthquakes, wildfires, landslides) strike anywhere in the world, CrisisGrid:

1. Ingests aerial / drone / street imagery alongside spoken field-responder radio reports.
2. Segments physical hazards vs. passable infrastructure.
3. Mathematically verifies safe evacuation corridors and drone / helicopter landing zones.
4. Autonomously generates multi-unit rescue dispatch protocols and visual tactical maps.

The system must never present an unverified model guess as a safe route. Model output is a *proposal*; deterministic local Python code is the *verifier*.

## 2. Strict Infrastructure Constraint (Non-Negotiable)

- Build **100%** of the AI inference using **ONLY** the official Meta Model API at `https://api.meta.ai/v1`, authenticated via a **single** `MODEL_API_KEY` environment variable.
- Permitted free, non-AI external data sources: **OpenStreetMap Overpass API** and **USGS APIs** only.
- Permitted local compute: free local Python verification (geometry, IoU, area, routing checks).
- **Do NOT** use paid external APIs, third-party cloud GPU providers, or any other model provider (no OpenAI / Anthropic / Google / Replicate / etc. inference endpoints).
- The OpenAI Python SDK is used **only as an HTTP client** pointed at `base_url="https://api.meta.ai/v1"`. It is not an inference provider in this project.
- Never hard-code an API key. Never commit `.env`. Never log, return, or expose `MODEL_API_KEY` in API responses, traces, or frontend code.

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MODEL_API_KEY"],
    base_url="https://api.meta.ai/v1",
)
```

## 3. Official Meta Model API Reference (Do Not Hallucinate Other Endpoints)

All calls use Base URL `https://api.meta.ai/v1` with header `Authorization: Bearer $MODEL_API_KEY`.

### 3.1 Spatial Hazard & Infrastructure Segmentation — `sam-3.1`

- Endpoint: `POST https://api.meta.ai/v1/responses` (via OpenAI SDK `client.responses.create`).
- **CRITICAL RULE:** `sam-3.1` accepts **ONE short concrete noun phrase per request** (e.g. `"flooded road"`, `"debris"`, `"bridge"`, `"clear flat ground"`, `"damaged building"`, `"stranded vehicle"`). Send **parallel async requests** for multiple concepts. Never pack multiple concepts into one prompt.
- Request format:

```python
response = client.responses.create(
    model="sam-3.1",
    input=[{
        "type": "message",
        "role": "user",
        "content": [
            {"type": "input_text", "text": "flooded road"},
            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64_img}"}
        ]
    }]
)
```

- Output wire format: text in `output_text` formatted as:

```
<0f>0<|box;x1=181;y1=365;x2=556;y2=486;w=1516;h=1600|><|mask;x=0;y=0;data=...|>
```

- Parse `x1, y1, x2, y2, w, h` and RLE mask payloads with a **deterministic regex parser** (see `backend/services/sam_parser.py`). Never use an LLM to parse SAM output.

Canonical concept sets (Day 2, `backend/services/sam_hazard_scanner.py`):

- **Passable Infrastructure:** `road`, `bridge`, `clear flat ground`, `rooftop`
- **Critical Hazards:** `flood water`, `debris`, `fire`, `damaged building`, `stranded vehicle`

### 3.2 Emergency Radio / Field Voice Transcription — `muse-voice-transcribe-1.0`

- Endpoint: `POST https://api.meta.ai/v1/asr/transcribe` (multipart form-data):

```bash
curl -X POST https://api.meta.ai/v1/asr/transcribe \
  -H "Authorization: Bearer $MODEL_API_KEY" \
  -F 'request={"mode":"ENDPOINTING","model":"muse-voice-transcribe-1.0","audioEncoding":"WAV"};type=application/json' \
  -F 'audio=@file.wav'
```

- Always include a clean **text-input fallback** for quick browser testing when no audio is available.

### 3.3 Multimodal Triage & Tool Reasoning — `muse-spark-1.3`

- Endpoint: `client.responses.create(model="muse-spark-1.3", input=[...])` or `client.chat.completions.create(model="muse-spark-1.3", messages=[...])`.
- Prefer role `"developer"` over `"system"` for instructions.
- Use for multimodal damage & urgency assessment and for proposing evacuation corridors that the deterministic verifier then checks. Spark proposes; Python disposes.

### 3.4 High-Effort Autonomous Dispatch Coordinator — `muse-wonder-1.0`

- Endpoint: `client.responses.create(model="muse-wonder-1.0", reasoning={"effort": "high"}, input=[...])`.
- Synthesizes **verified** hazard data only (never raw unverified proposals) into autonomous multi-unit emergency response actions: medical, heavy debris clearance, aerial drop, etc.

### 3.5 Tactical Rescue Map & Briefing Card Generator — `muse-image-1.0`

- Endpoint: `client.images.generate(model="muse-image-1.0", prompt="...", output_format="png")` or multimodal edit via `client.responses.create(model="muse-image-1.0", input=[...])`.
- Generated briefing cards are summaries of verified state; they must not invent hazards, routes, or unit positions not present in the verified data.

## 4. Verifiable-Agent Principle (Core Differentiator)

1. `sam-3.1` segments hazards and infrastructure (one phrase per request, in parallel).
2. `muse-voice-transcribe-1.0` + `muse-spark-1.3` add field-report context and urgency.
3. **Deterministic Python verifier** (`backend/services/verifiable_corridor_engine.py`, Day 4) calculates hazard-to-road intersection (IoU), checks minimum safe clearance area for drone/helicopter landing zones, and cross-checks OpenStreetMap roads/hospitals.
4. If a `muse-spark-1.3`-proposed path crosses a segmented hazard mask, the verifier **forces a re-route**. No unverified corridor is ever marked safe.
5. Only verified state flows into `muse-wonder-1.0` dispatch and `muse-image-1.0` briefing cards.
6. Every step is emitted to the frontend **Verifiable Agent Trace** so judges can audit *why* a corridor was accepted or rejected.

## 5. Repository Layout

```
CrisisGrid/
├── AGENTS.md                  # This file (binding)
├── ROADMAP.md                 # 9-Day Global Frontier Build Plan (Oct 27 – Nov 4, 2026)
├── README.md                  # Public README (finalised Day 9)
├── .env.example               # MODEL_API_KEY template — copy to .env, never commit .env
├── .gitignore
├── backend/
│   ├── main.py                # FastAPI app (Day 1 scaffold)
│   ├── config.py              # Env / settings (MODEL_API_KEY, META base URL)
│   ├── requirements.txt
│   ├── test_meta_api.py       # Day 1 Meta Model API smoke test — run this first
│   ├── README.md
│   └── services/
│       ├── __init__.py
│       ├── sam_parser.py              # Deterministic regex parser for sam-3.1 wire format (Day 1)
│       ├── sam_hazard_scanner.py      # Day 2: parallel sam-3.1 segmentation
│       ├── voice_and_triage.py        # Day 3: muse-voice-transcribe-1.0 + muse-spark-1.3
│       ├── verifiable_corridor_engine.py  # Day 4: deterministic verifier + OSM/USGS
│       └── wonder_commander.py        # Day 5: muse-wonder-1.0 + muse-image-1.0
└── frontend/
    ├── package.json           # Next.js (App Router, TypeScript)
    ├── app/                   # Neo-Brutalist Tactical Command UI (Day 1 shell, Day 6 full build)
    ├── components/            # TacticalCanvas, AgentTrace, DispatchConsole
    └── lib/api.ts             # Typed client for the FastAPI backend
```

## 6. Coding Rules

- **Backend:** Python 3.11+, FastAPI, `httpx` / OpenAI SDK pointed only at `https://api.meta.ai/v1`. Async for all parallel `sam-3.1` concept requests. Pydantic models for every API request/response.
- **Frontend:** Next.js App Router + TypeScript. Neo-Brutalist Tactical Command style: high contrast, thick black borders, hard offset shadows, no gradients, no rounded-corner SaaS look. Green = passable / verified landing zone, Red = hazard / blocked, Yellow = caution / unverified.
- **Determinism:** Geometry, IoU, clearance-area, and parsing logic must be pure, unit-testable Python with no model calls inside.
- **Secrets:** Only `MODEL_API_KEY` (backend) and `NEXT_PUBLIC_API_BASE_URL` (frontend, non-secret) may be read from env. See `.env.example`.
- **Errors:** If `MODEL_API_KEY` is missing, fail with a clear human-readable message pointing at `.env.example` — never a stack trace shown to judges, never a silent fallback to another provider.
- **No placeholder deception:** Stub endpoints must return an explicit `501` / `status: "not_implemented"` with the roadmap day they land. Never fake segmentation, transcription, or dispatch output.
- **Testing:** Run `python backend/test_meta_api.py` before any demo. Its offline parser self-test must pass with no key and no network.

## 7. Quick Start

```bash
cp .env.example .env          # then set MODEL_API_KEY
pip install -r backend/requirements.txt
python backend/test_meta_api.py            # offline self-test + env check
python backend/test_meta_api.py --live     # + live muse-spark-1.3 ping (needs key)
uvicorn backend.main:app --reload --port 8000
cd frontend && npm install && npm run dev  # http://localhost:3000
```

## 8. Build Plan

Follow `ROADMAP.md` day by day (Day 1 = Oct 27 … Day 9 = Nov 4, 2026). Do not skip the Day 4 verifier — it is the trust layer the entire "Push the Frontier" claim rests on.
