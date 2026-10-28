# CrisisGrid Frontend — Neo-Brutalist Tactical Command UI

Built with **Next.js 14 (App Router)**, **React 18**, and **TypeScript**. Designed in a high-contrast **Neo-Brutalist Tactical Command** aesthetic engineered for emergency operations centers: thick black structural borders, hard offset shadows, monospace telemetry, zero decorative gradients, and strict semantic colour discipline.

---

## ⚡ Quick Start

```bash
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm install
npm run dev                        # Opens http://localhost:3000
```

> **Note:** Start the FastAPI backend on port `8000` (`uvicorn backend.main:app --reload --port 8000` from the repo root) so the status strip and API client connect live.

---

## 🎨 Tactical Colour Law (`AGENTS.md` §6)

The frontend enforces a strict visual trust hierarchy so operators and judges can immediately distinguish raw neural proposals from mathematically verified routes:

| Colour | Hex | CSS Swatch | Meaning |
| :--- | :---: | :---: | :--- |
| **Green** | `#00C853` | `.sw-green` / `.tag-green` | Passable infrastructure (`road`, `bridge`, `clear flat ground`, `rooftop`) OR corridor/landing zone **mathematically verified** by `verifiable_corridor_engine.py`. |
| **Red** | `#FF2D20` | `.sw-red` / `.tag-red` | Critical hazard (`flood water`, `debris`, `fire`, `damaged building`, `stranded vehicle`) OR candidate **rejected** due to $>10\%$ hazard intersection / insufficient clearance. |
| **Yellow** | `#FFD600` | `.sw-yellow` / `.tag-yellow` | **Unverified proposal** from `muse-spark-1.3` awaiting deterministic Python verification, OR unit held by the post-Wonder guardrail. |

---

## 🗂️ Component & Client Layout

- **[`app/page.tsx`](./app/page.tsx):** Root Tactical Command dashboard (Days 6–8). Polls `GET /health` on mount, displays live backend & `MODEL_API_KEY` readiness (without ever exposing the key), and runs the full judge flow from Mission Control: 1-click Global Disaster Presets, drag-drop image upload, text/WAV field report, optional OSM lat/lon, staged `STEP 1 SCAN -> STEP 2 TRIAGE -> STEP 3 VERIFY -> STEP 4 DISPATCH` buttons plus one-click `POST /api/run-crisisgrid`. Re-running an upstream stage clears downstream state.
- **[`components/PresetPanel.tsx`](./components/PresetPanel.tsx) & [`lib/presets.ts`](./lib/presets.ts):** Day 8 1-Click Global Disaster Presets (`urban-flood`, `earthquake-bridge`, `wildfire-helipad`) with **RUN** (full live pipeline) and **LOAD ONLY** actions, expected-focus tags, and declared provenance.
- **[`components/TacticalCanvas.tsx`](./components/TacticalCanvas.tsx):** Interactive HTML5 `<canvas>` viewport (Days 6–7): source image with `sam-3.1` detection boxes, corridor polylines and landing-zone circles coloured strictly by verifier state, per-concept layer toggles, click-to-inspect, hover coordinates, and Before/After Damage Delta view.
- **[`components/AgentTrace.tsx`](./components/AgentTrace.tsx):** Live **Verifiable Agent Trace** (Day 6): merged scan/triage/verify/dispatch/delta events with verified/rejected/caution filters, counts, auto-scroll and latency metadata - every `sam-3.1` concept scan, `muse-spark-1.3` proposal, deterministic IoU proof, rejection reason and forced re-route.
- **[`components/DispatchConsole.tsx`](./components/DispatchConsole.tsx):** Dispatch Action Console (Day 6): STEP 4 gated on `dispatch_ready`, `muse-wonder-1.0` unit table (green dispatched / yellow guardrail-held with stripped targets), phases, safety brief, guardrail audit and the inline `muse-image-1.0` briefing card.
- **[`components/Day7Panels.tsx`](./components/Day7Panels.tsx):** Before/After Damage Delta (`POST /api/delta`), Post-Clearance Re-Verification (`POST /api/delta/verify-clearance`), and Multi-Sector Triage Ranking (`POST /api/sectors/rank`) panels.
- **[`lib/api.ts`](./lib/api.ts):** Fully typed TypeScript SDK covering all 18 backend endpoints:
  - `fetchHealth()` (`GET /health`)
  - `fetchScanConcepts()` & `scanHazards()` (`GET /api/scan-hazards/concepts`, `POST /api/scan-hazards`)
  - `triageReport()` & `triageText()` (`POST /api/triage`, `POST /api/triage/text`)
  - `verifyCandidates()` (`POST /api/verify`)
  - `dispatchVerified()` & `runCrisisGrid()` (`POST /api/dispatch`, `POST /api/run-crisisgrid`)
  - `computeDelta()`, `verifyClearance()`, & `rankSectors()` (`POST /api/delta`, `POST /api/delta/verify-clearance`, `POST /api/sectors/rank`)
  - `fetchPresets()` (`GET /api/presets`)
