# CrisisGrid — 3-Minute Technical Demonstration Script

This document provides the structured timecoded script and operational sequence for demonstrating CrisisGrid's autonomous disaster triage and verification pipeline.

---

## Technical Prerequisites

- **Backend:** FastAPI service running on `http://localhost:8000` (`uvicorn backend.main:app --reload --port 8000`).
- **Frontend:** Next.js Mission Control running on `http://localhost:3000` (`cd frontend && npm run dev`).
- **Environment:** `MODEL_API_KEY` configured in `.env` (or local open-weight server configured via `META_API_BASE_URL`).

---

## Demonstration Sequence

### 1. System Overview & Architecture (`0:00 – 0:25`)
- **Visual:** Focus on the top telemetry bar (`BACKEND: ONLINE`, `MODEL_API_KEY: CONFIGURED`, `API: api.meta.ai/v1`) and the 6-stage pipeline ribbon.
- **Narrative:**
  > "During natural disasters, emergency operation centers spend critical time cross-referencing aerial drone imagery, radio dispatches, and infrastructure maps. Standard vision-language models frequently propose evacuation corridors that traverse active hazards. CrisisGrid integrates five Meta frontier models on `api.meta.ai/v1`, governed by a deterministic local Python geometry verifier. Model outputs serve as proposals; deterministic mathematics verifies or rejects them."

### 2. Multi-Concept Segmentation & Radio ASR (`0:25 – 1:00`)
- **Visual:** In **Global Disaster Presets**, select **Urban Flood Corridor** (`urban-flood.jpg` + `field-radio.wav`). Execute **Step 1: Scan Hazards** and **Step 2: Voice + Triage**.
- **System Behavior:**
  - `sam-3.1` fans out 9 parallel single-phrase async requests, segmenting passable road infrastructure (green) and floodwater hazards (red).
  - `muse-voice-transcribe-1.0` decodes the 16kHz mono WAV transmission into a grounded field report.
  - `muse-spark-1.3` evaluates scene severity and proposes initial candidate evacuation corridors and landing zones rendered in dashed yellow (`unverified_candidate`).
- **Narrative:**
  > "`sam-3.1` executes nine parallel single-phrase requests to segment roads and hazard boundaries simultaneously. Concurrently, `muse-voice-transcribe-1.0` transcribes the first responder's radio report. `muse-spark-1.3` synthesizes the multimodal data into incident priorities and initial corridor proposals, flagged in yellow as unverified candidates."

### 3. Deterministic Verification & Closed-Loop Re-Route (`1:00 – 1:45`)
- **Visual:** Execute **Step 3: Verify Corridors** and inspect the **Verifiable Agent Trace**.
- **System Behavior:**
  - `verifiable_corridor_engine.py` evaluates the candidate path against segmented hazard masks.
  - The initial corridor intersects floodwater with $>10\%$ overlap; the verifier deterministically rejects the path (`REJECTED`) and outputs exact geometric evidence.
  - Bounded re-route loop triggers `muse-spark-1.3` to propose an alternative path avoiding the hazard polygon.
  - The revised corridor verifies with $0.0\%$ hazard contact and $\ge 50\%$ passable road support, updating status to `VERIFIED` (green) and querying nearby medical facilities via OpenStreetMap Overpass.
- **Narrative:**
  > "The deterministic Python verifier calculates exact polygon intersection. When the initial proposal crosses floodwater, Python rejects the path and returns geometric proof to Spark. Spark autonomously re-routes along the dry asphalt, achieving zero hazard contact and earning deterministic verification."

### 4. High-Effort Dispatch & Briefing Generation (`1:45 – 2:30`)
- **Visual:** Execute **Step 4: Autonomous Dispatch** in the Dispatch Action Console.
- **System Behavior:**
  - `muse-wonder-1.0` (`reasoning={"effort": "high"}`) synthesizes a multi-unit emergency protocol (medical, swiftwater rescue, logistics) constrained strictly to verified corridors and landing zones.
  - Post-generation Python guardrail audits assignments, holding any unit mapped to unverified geometry.
  - `muse-image-1.0` generates a high-contrast tactical briefing card schematic from verified facts.
- **Narrative:**
  > "Only verified coordinates are passed to `muse-wonder-1.0` running high-effort reasoning. Our secondary Python guardrail verifies every unit dispatch assignment before execution. `muse-image-1.0` then synthesizes a tactical field briefing card strictly from verified mission parameters."

### 5. Post-Clearance Verification & Multi-Sector Triage (`2:30 – 3:00`)
- **Visual:** Review the **Before / After Damage Delta** panel and execute **Rank Sectors**.
- **System Behavior:**
  - `compute_damage_delta` matches before and after hazard masks via greedy bounding-box IoU.
  - `verify_clearance` re-evaluates previously blocked routes, transitioning status from `REJECTED` to `VERIFIED` only upon confirming physical hazard clearance.
  - `rank_sectors` scores multiple operational zones across a transparent $0\text{–}100$ priority formula.
- **Narrative:**
  > "As rescue teams clear debris, CrisisGrid monitors post-clearance imagery and updates corridor safety deterministically. Across widespread emergencies, the multi-sector triage engine ranks zones mathematically to optimize resource allocation."
