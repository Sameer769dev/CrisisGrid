# CrisisGrid — 3-Minute Master Demo Video & Audio Editing Guide
**Meta Global AI Developer Hackathon: "Push the Frontier"**  
**Project:** CrisisGrid (Autonomous Multimodal Disaster Triage & Emergency Dispatch Agent)  
**Total Running Time:** 2 minutes 42 seconds (162.00s) — *Strictly below the 3-minute hard ceiling*

---

## 1. Master Files Directory

All render deliverables are located in your project directory:

| Deliverable Asset | File Path | Format & Specs |
|---|---|---|
| **Clean Screen Recording** | `docs/CrisisGrid_3Min_Clean_Screen_Recording.mp4` | 1080p (1920x1080), 30 fps, H.264, no burnt-in text/watermarks |
| **Complete Reference Demo** | `docs/CrisisGrid_3Min_Complete_Demo.mp4` | 1080p MP4 with synced mixed voiceover & tactical SFX |
| **Master Voiceover Stem** | `docs/CrisisGrid_3Min_Master_Voiceover.wav` | 44.1 kHz, 16-bit Stereo PCM (Pure dialogue stem, Gemini 3.8 Flash TTS "Puck") |
| **Master Audio (Mixed)** | `docs/CrisisGrid_3Min_Master_Audio_Mixed.wav` | 44.1 kHz, 16-bit Stereo PCM (Dialogue + subtle tactical SFX + ambient drone) |
| **Individual Voice Acts** | `demo_3min/voice/act1_intro_hook.wav`<br>`demo_3min/voice/act2_sam_and_voice.wav`<br>`demo_3min/voice/act3_triage_and_reroute.wav`<br>`demo_3min/voice/act4_wonder_dispatch.wav`<br>`demo_3min/voice/act5_usgs_clearance_outro.wav` | Individual 24kHz/44.1kHz stems for modular rearrangement in your NLE timeline |

---

## 2. Second-by-Second Timecode Alignment & Motion Graphic Cue Sheet

Use this timeline to drop markers, title cards, zooms, and lower-thirds in Adobe Premiere Pro, DaVinci Resolve, Final Cut Pro, or CapCut:

```
[0:00 - 0:33] ACT 1: THE CRISIS HOOK & MULTIMODAL INGESTION
[0:33 - 1:00] ACT 2: 9x PARALLEL SAM-3.1 SCAN & MUSE VOICE TRANSCRIBE
[1:00 - 1:32] ACT 3: MULTIMODAL SPARK-1.3 TRIAGE & DETERMINISTIC GEOMETRIC RE-ROUTE
[1:32 - 2:08] ACT 4: HIGH-EFFORT WONDER-1.0 DISPATCH & TACTICAL BRIEFING CARD
[2:08 - 2:42] ACT 5: LIVE USGS SEISMIC TELEMETRY & CLEARANCE VERIFICATION OUTRO
```

---

### Act 1: The Crisis Hook & Multimodal Ingestion (0:00 – 0:33)

- **Exact Timecode:** `0:00 – 0:33` (Duration: 33 seconds)
- **Voiceover Text (Gemini 3.8 Flash TTS):**
  > *"When natural disasters strike anywhere in the world, emergency operations centers lose forty-five critical minutes manually cross-referencing aerial drone footage, chaotic radio chatter, and static maps. Worse, off-the-shelf vision models routinely hallucinate safe evacuation routes straight through twelve feet of raging floodwater. CrisisGrid is an autonomous multimodal disaster triage and emergency dispatch agent built on five Meta frontier models. Neural models propose; pure deterministic Python mathematics disposes."*
- **On-Screen Action:**
  - `0:00 - 0:08`: Screen rests on CrisisGrid Tactical Command top header, showing the **ONLINE** backend badge and the **5 Meta Models Strip** (`sam-3.1`, `muse-voice-transcribe-1.0`, `muse-spark-1.3`, `muse-wonder-1.0`, `muse-image-1.0`).
  - `0:08 - 0:14`: Smooth camera scroll down to the **Built-in 9-Scene Disaster Test Gallery**.
  - `0:14 - 0:21`: Category filter pills are clicked: `EARTHQUAKE` $\rightarrow$ `LANDSLIDE` $\rightarrow$ `FLOOD`.
  - `0:21 - 0:26`: Operator clicks **LOAD SCENE** on the Urban Flood test scene.
  - `0:26 - 0:33`: Camera smoothly scrolls back up to Mission Control, displaying the high-resolution aerial disaster image, radio WAV audio file, and target GPS coordinates loaded and armed.
- **Recommended Post-Production Graphics:**
  - `0:00 - 0:04`: Dramatic title card: **CRISISGRID // AUTONOMOUS DISASTER DISPATCH AGENT**.
  - `0:05 - 0:10`: Lower-third badge: **META GLOBAL AI DEVELOPER HACKATHON // PUSH THE FRONTIER**.
  - `0:12 - 0:18`: Zoom punch-in on the 9-scene disaster presets.
  - `0:28 - 0:32`: Callout box over the loaded aerial photo & emergency radio WAV.

---

### Act 2: 9x Parallel SAM-3.1 Scan & Muse Voice Transcribe (0:33 – 1:00)

- **Exact Timecode:** `0:33 – 1:00` (Duration: 27 seconds)
- **Voiceover Text (Gemini 3.8 Flash TTS):**
  > *"In one click, CrisisGrid launches nine parallel sam three point one segmentation calls, separating passable infrastructure like roads and bridges from critical hazards like floodwater, debris, and damaged buildings in just five seconds. Simultaneously, muse-voice-transcribe-one-point-zero processes incoming responder radio audio, decoding the field unit's mayday transmission directly into structured text with over ninety-nine percent accuracy."*
- **On-Screen Action:**
  - `0:33 - 0:36`: Operator clicks **RUN FULL PIPELINE** (`/api/run-crisisgrid`).
  - `0:36 - 0:44`: The **Live Telemetry HUD** activates at the top, with active execution timer and stage chips (`1. SAM-3.1 9x PARALLEL`, `2. VOICE + SPARK-1.3`, `3. PYTHON VERIFIER`, `4. WONDER-1.0`).
  - `0:44 - 1:00`: Camera scrolls smoothly to the **Tactical Canvas & Live Agent Trace**. 8 physical detections and masks materialize: floodwater in bright tactical red, dry road segments in green. In the side trace panel, the radio transmission is transcribed in real-time.
- **Recommended Post-Production Graphics:**
  - `0:34 - 0:38`: Sound effect whoosh + visual speed counter: **"9x ASYNC META SAM-3.1 INFERENCE"**.
  - `0:42 - 0:48`: Split callout showing parallel processing: Left = **SAM-3.1 Spatial Segmentation** / Right = **Muse Voice Transcribe 1.0**.
  - `0:52 - 0:58`: Zoom box highlighting the red floodwater polygons and green passable road vector.

---

### Act 3: Multimodal Spark-1.3 Triage & Deterministic Geometric Re-Route (1:00 – 1:32)

- **Exact Timecode:** `1:00 – 1:32` (Duration: 32 seconds)
- **Voiceover Text (Gemini 3.8 Flash TTS):**
  > *"Next, muse-spark-one-point-three fuses the radio call with the segmented aerial imagery to evaluate damage severity and propose candidate evacuation corridors. Notice that Spark proposes in dashed yellow, unverified by design. When its initial proposed route cuts across segmented floodwater past our strict ten percent tolerance, our deterministic Liang-Barsky geometry engine instantly rejects it with mathematical proof, forcing an autonomous self-correction loop onto dry elevated asphalt. Zero percent hazard contact: Corridor One verified."*
- **On-Screen Action:**
  - `1:00 - 1:12`: Agent Trace scrolls through the exact mathematical audit trail:
    - *Spark Proposal* (Dashed Yellow Corridor)
    - *Liang-Barsky Line-Box Hazard Intersection test: 38.4% flood overlap (>10% limit)* $\rightarrow$ **STATUS: REJECTED (RED)**
    - *Autonomous Re-Route Triggered* $\rightarrow$ Candidate 1B shifted north to elevated road
    - *Geometric Re-Test: 0.0% hazard intersection* $\rightarrow$ **STATUS: VERIFIED (GREEN)**
  - `1:12 - 1:22`: Mouse cursor clicks directly on the tactical canvas corridor and the helicopter landing zone circle to inspect real-time polygon coordinates and clearance radius ($r = 18\text{m}$, $>15\text{m}$ required).
  - `1:22 - 1:32`: Smooth scroll to the **Triage & Candidate Assessment** panel, highlighting **CRITICAL SEVERITY (URGENCY 92/100)**, People at Risk estimate (12 on rooftops), and OpenStreetMap hospital query.
- **Recommended Post-Production Graphics:**
  - `1:03 - 1:10`: Red flashing alert badge: **"MODEL PROPOSAL REJECTED: 38.4% FLOOD HAZARD OVERLAP"**.
  - `1:14 - 1:20`: Neon green badge: **"DETERMINISTIC VERIFICATION: 0.0% OVERLAP // ROUTE CLEARED"**.
  - `1:25 - 1:30`: Highlight box around the **OpenStreetMap Facilities** (e.g. Tribhuvan Teaching Hospital 1,420m away).

---

### Act 4: High-Effort Wonder-1.0 Dispatch & Tactical Briefing Card (1:32 – 2:08)

- **Exact Timecode:** `1:32 – 2:08` (Duration: 36 seconds)
- **Voiceover Text (Gemini 3.8 Flash TTS):**
  > *"Only mathematically verified coordinates are allowed to reach muse-wonder-one-point-zero for high-effort tactical dispatch reasoning. A strict Python guardrail holds back any rescue unit targeted at an unverified zone. Wonder synthesizes a comprehensive five-unit multi-agency allocation: aerial drone scouts, swift-water boats, and medical staging. Alongside, muse-image-one-point-zero renders an official tactical briefing card from verified facts only, and one click exports the complete FEMA Incident Action Plan."*
- **On-Screen Action:**
  - `1:32 - 1:44`: Camera scrolls to the **Dispatch Action Console** (`muse-wonder-1.0`). Status tag shows **ARMED - VERIFIED** in bright green.
  - `1:44 - 1:54`: Operator hovers through the **5-Unit Multi-Agency Dispatch Table**:
    - `DRONE-ALPHA`: Aerial reconnaissance over flooded residential grid
    - `BOAT-BRAVO`: Swift-water rescue team deployed along Corridor 1
    - `MED-STAGING-1`: Mobile triage unit deployed at Verified Landing Zone A
    - `DEBRIS-TASKFORCE-3`: Heavy equipment clearing north bridge approach
  - `1:54 - 2:00`: Operator hovers over the **Muse-Image-1.0 Tactical Briefing Card** preview.
  - `2:00 - 2:08`: Operator clicks **EXPORT IAP (.MD)** and hovers over **EXPORT JSON (.JSON)**, instantly downloading the standardized Incident Action Plan.
- **Recommended Post-Production Graphics:**
  - `1:35 - 1:40`: Callout: **"REASONING EFFORT: HIGH // 0 UNVERIFIED TARGETS PERMITTED"**.
  - `1:46 - 1:52`: Graphic overlay accentuating the 5 dispatch units with icons (Drone, Boat, Medical, Heavy Cleared).
  - `2:02 - 2:07`: Notification banner: **"INCIDENT ACTION PLAN (FEMA ICS-204) EXPORTED"**.

---

### Act 5: Live USGS Seismic Telemetry & Clearance Verification Outro (2:08 – 2:42)

- **Exact Timecode:** `2:08 – 2:42` (Duration: 34 seconds)
- **Voiceover Text (Gemini 3.8 Flash TTS):**
  > *"To handle cascading crises, CrisisGrid streams live global earthquakes directly from the USGS seismic feed. Dispatchers can select real epicenters to query nearby hospitals and shelters via OpenStreetMap. Finally, our clearance delta engine monitors post-engineering scenes, re-scanning cleared bridges and flipping their status from blocked to green only when new physical geometry verifies safe passage. Five Meta frontier models. One API key. Zero unverified guesses."*
- **On-Screen Action:**
  - `2:08 - 2:18`: Camera scrolls down to the **Live USGS Seismic Telemetry** module in the Preset panel. Operator clicks **FETCH LIVE M4.5+ (PAST 24H)**. A live table of global seismic events streams in instantly with magnitudes, locations, and coordinates.
  - `2:18 - 2:32`: Camera scrolls to the **Before / After Damage Delta & Post-Clearance Re-Verifier** panel:
    - Operator clicks **LOAD BEFORE + AFTER PAIR** (Earthquake Bridge Rubble $\rightarrow$ Post-Clearance Reopened Bridge).
    - Operator clicks **1-CLICK RUN BEFORE → AFTER CLEARANCE**.
    - The clearance engine runs SAM-3.1 on the cleared frame, computes the delta (-85% rubble), re-runs the deterministic geometry engine, and flips the corridor from **BLOCKED (RED) $\rightarrow$ VERIFIED (GREEN)**.
  - `2:32 - 2:42`: Camera smoothly scrolls back to the top of the interface for a clean, professional outro hold on the CrisisGrid header.
- **Recommended Post-Production Graphics:**
  - `2:10 - 2:15`: Lower-third badge: **"LIVE USGS SENSOR FEED // REAL-TIME GLOBAL SEISMIC DATA"**.
  - `2:24 - 2:30`: Side-by-side comparison slider: **"BEFORE: 100% BLOCKED RUBBLE" vs "AFTER: RE-OPENED & VERIFIED"**.
  - `2:36 - 2:42`: Outro title card:
    - **CRISISGRID**
    - **5 Meta Models · 1 API Key · Pure Verifiable AI**
    - **Meta Global AI Developer Hackathon 2026**

---

## 3. Recommended NLE Setup (Premiere / DaVinci / Final Cut)

1. **Project Settings:** 1920x1080 resolution, 30.00 fps or 29.97 fps, Rec.709 color space.
2. **Audio Track Setup:**
   - **A1:** `docs/CrisisGrid_3Min_Master_Voiceover.wav` (Normalized at -1.0 dB True Peak, dialogue LUFS: -16 LUFS).
   - **A2:** Your custom music bed (keep at -22 dB to -26 dB during speech so dialogue cuts through cleanly).
   - **A3:** SFX / UI interface sounds (already included in `master_audio_mixed.wav`, or add custom whooshes/chimes).
3. **Video Track Setup:**
   - **V1:** `docs/CrisisGrid_3Min_Clean_Screen_Recording.mp4` (Base software recording, clean without burnt-in text).
   - **V2:** Zooms & Pan/Crop adjustments (e.g. 115% zoom into the Tactical Canvas during Act 2 and 3).
   - **V3:** Motion graphics, text callouts, bounding boxes, and transition overlays.
4. **Export Settings:**
   - Container: MP4 (H.264 / AAC)
   - Profile: High, Level 4.2
   - Bitrate: 15–20 Mbps (VBR 2-pass or CBR)
   - Audio: AAC 320 kbps, 48 kHz / 44.1 kHz Stereo
   - Target Total Length: Exactly 2:42 (162 seconds), comfortably under the 3:00 limit.

