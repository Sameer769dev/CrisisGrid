import os
import re

def build_complete_ass():
    print("=" * 70)
    print("CRISISGRID — GENERATING COMPLETE TACTICAL HUD OVERLAYS & SUBTITLES")
    print("=" * 70)

    header = """[Script Info]
Title: CrisisGrid Tactical HUD & Tactical Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Subtitle,Impact,50,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4.5,2.0,2,40,40,65,1
Style: HUD_Cyan,Impact,34,&H00FFE500,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,1,0,3,7.0,0.0,8,40,40,45,1
Style: HUD_Yellow,Impact,34,&H0000E6FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,1,0,3,7.0,0.0,8,40,40,45,1
Style: HUD_RedAlert,Impact,38,&H00FFFFFF,&H000000FF,&H001818DC,&H001818DC,-1,0,0,0,100,100,1,0,3,8.0,0.0,8,40,40,45,1
Style: HUD_GreenVerified,Impact,38,&H00000000,&H000000FF,&H0020FF00,&H0020FF00,-1,0,0,0,100,100,1,0,3,8.0,0.0,8,40,40,45,1
Style: IntroTitle,Impact,74,&H0000E6FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,5.5,3.0,5,40,40,40,1
Style: OutroTitle,Impact,72,&H00FFE500,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,5.5,3.0,5,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []

    # =========================================================================
    # 1. TACTICAL HUD OVERLAYS & TITLE CARDS (Upper / Middle Layers 2 & 3)
    # =========================================================================

    # --- ACT 1 (0:00 - 0:33) ---
    # 0:00 - 0:05: Fullscreen Intro Title Card
    events.append("Dialogue: 3,0:00:00.60,0:00:05.20,IntroTitle,,0,0,0,,CRISISGRID\\N{\\fs38\\c&H00FFFFFF&}AUTONOMOUS DISASTER DISPATCH AGENT")
    # 0:05 - 0:08: Digital glitch transition into V1 (Header)
    events.append("Dialogue: 2,0:00:05.40,0:00:08.50,HUD_Cyan,,0,0,0,,[ 5 META FRONTIER MODELS · 1 API KEY · ZERO UNVERIFIED GUESSES ]")

    # --- ACT 2 (0:33 - 1:00) ---
    # 0:37 - 0:44: Zoom 125% on Telemetry HUD timer ticking live
    events.append("Dialogue: 2,0:00:36.50,0:00:43.80,HUD_Yellow,,0,0,0,,⚡ 9x ASYNC SAM-3.1 SEGMENTATION CALLS // 5.2s TOTAL LATENCY")
    # 0:44 - 0:52: Pan down to Tactical Canvas / Responder radio
    events.append("Dialogue: 2,0:00:44.20,0:00:52.00,HUD_Cyan,,0,0,0,,🎙️ MUSE-VOICE-TRANSCRIBE-1.0 // MAYDAY RADIO CALL DECODED")

    # --- ACT 3 (1:00 - 1:32) ---
    # 1:08 - 1:15: Verifier flags 38.4% flood overlap
    events.append("Dialogue: 2,0:01:08.50,0:01:15.50,HUD_RedAlert,,0,0,0,,⚠️ PROPOSAL REJECTED: 38.4% HAZARD OVERLAP (LIANG-BARSKY AUDIT)")
    # 1:15 - 1:22: Autonomous self-correction shifts corridor to dry asphalt
    events.append("Dialogue: 2,0:01:15.80,0:01:23.00,HUD_GreenVerified,,0,0,0,,✓ DETERMINISTIC PROOF: 0.0% HAZARD CONTACT // CORRIDOR 1 VERIFIED")

    # --- ACT 4 (1:32 - 2:08) ---
    # 1:32 - 1:40: Pan to Dispatch Console
    events.append("Dialogue: 2,0:01:32.50,0:01:40.50,HUD_Yellow,,0,0,0,,🛡️ MUSE-WONDER-1.0 // REASONING EFFORT: HIGH [ARMED - VERIFIED]")

    # --- ACT 5 (2:08 - 2:42) ---
    # 2:08 - 2:16: USGS Live Seismic Telemetry
    events.append("Dialogue: 2,0:02:08.00,0:02:16.00,HUD_Cyan,,0,0,0,,🌐 LIVE USGS SEISMIC TELEMETRY // REAL-TIME GLOBAL M4.5+ SENSOR FEED")
    # 2:24 - 2:32: Blocked bridge flips RED -> GREEN
    events.append("Dialogue: 2,0:02:24.00,0:02:32.00,HUD_GreenVerified,,0,0,0,,✓ CLEARANCE DELTA ENGINE: STATUS FLIPPED [BLOCKED ➔ VERIFIED GREEN]")
    # 2:33 - 2:42: Final Fullscreen Outro Title Card
    events.append("Dialogue: 3,0:02:33.50,0:02:42.00,OutroTitle,,0,0,0,,CRISISGRID\\N{\\fs36\\c&H00FFFFFF&}5 META FRONTIER MODELS · 1 API KEY · PURE VERIFIABLE AI\\N{\\fs30\\c&H0000E6FF&}META GLOBAL AI DEVELOPER HACKATHON 2026")

    # =========================================================================
    # 2. MRBEAST CONTENT CREATOR DIALOGUE SUBTITLES (Lower-Third Layer 1)
    # =========================================================================
    speech_lines = [
        # --- ACT 1 (0:00 - 0:33) ---
        ("0:00:00.80", "0:00:03.40", "When natural disasters strike\\N{\\c&H0000E6FF&}ANYWHERE IN THE WORLD{\\c&H00FFFFFF&}"),
        ("0:00:03.50", "0:00:06.80", "emergency operations centers\\N{\\c&H002020FF&}LOSE 45 MINUTES{\\c&H00FFFFFF&}"),
        ("0:00:07.00", "0:00:09.80", "manually cross-referencing\\N{\\c&H0000E6FF&}AERIAL DRONE FOOTAGE{\\c&H00FFFFFF&}"),
        ("0:00:09.90", "0:00:12.80", "chaotic radio chatter\\Nand static maps."),
        ("0:00:13.00", "0:00:15.80", "Worse, off-the-shelf vision models\\N{\\c&H002020FF&}ROUTINELY HALLUCINATE{\\c&H00FFFFFF&}"),
        ("0:00:16.00", "0:00:19.40", "safe evacuation routes straight through\\N{\\c&H002020FF&}12 FEET OF FLOODWATER{\\c&H00FFFFFF&}!"),
        ("0:00:19.80", "0:00:23.50", "{\\c&H0000E6FF&}CRISISGRID{\\c&H00FFFFFF&} is an autonomous\\Nmultimodal triage and dispatch agent,"),
        ("0:00:23.70", "0:00:27.20", "built on {\\c&H0000E6FF&}FIVE META FRONTIER MODELS{\\c&H00FFFFFF&}."),
        ("0:00:27.50", "0:00:32.20", "Neural models propose;\\Npure deterministic Python {\\c&H0020FF00&}MATHEMATICS DISPOSES{\\c&H00FFFFFF&}."),

        # --- ACT 2 (0:33 - 1:00) ---
        ("0:00:33.00", "0:00:36.20", "In one click, CrisisGrid launches\\N{\\c&H0000E6FF&}9x PARALLEL SAM-3.1 CALLS{\\c&H00FFFFFF&},"),
        ("0:00:36.40", "0:00:40.00", "separating {\\c&H0020FF00&}PASSABLE INFRASTRUCTURE{\\c&H00FFFFFF&}\\Nfrom {\\c&H002020FF&}CRITICAL HAZARDS{\\c&H00FFFFFF&}"),
        ("0:00:40.20", "0:00:44.20", "like floodwater, debris, and damaged buildings\\N{\\c&H0000E6FF&}IN JUST 5 SECONDS{\\c&H00FFFFFF&}."),
        ("0:00:44.50", "0:00:48.00", "Simultaneously, {\\c&H0000E6FF&}MUSE-VOICE-TRANSCRIBE-1.0{\\c&H00FFFFFF&}\\Nprocesses responder radio audio,"),
        ("0:00:48.20", "0:00:52.20", "decoding the field unit's {\\c&H002020FF&}MAYDAY CALL{\\c&H00FFFFFF&}\\Ndirectly into structured text"),
        ("0:00:52.40", "0:00:57.50", "with {\\c&H0020FF00&}OVER 99% ACCURACY{\\c&H00FFFFFF&}."),

        # --- ACT 3 (1:00 - 1:32) ---
        ("0:01:00.00", "0:01:04.20", "Next, {\\c&H0000E6FF&}MUSE-SPARK-1.3{\\c&H00FFFFFF&} fuses the radio call\\Nwith segmented aerial imagery"),
        ("0:01:04.40", "0:01:08.50", "to evaluate {\\c&H002020FF&}DAMAGE SEVERITY{\\c&H00FFFFFF&}\\Nand propose candidate corridors."),
        ("0:01:08.80", "0:01:12.80", "Spark proposes in {\\c&H0000E6FF&}DASHED YELLOW{\\c&H00FFFFFF&},\\N{\\c&H0000E6FF&}UNVERIFIED BY DESIGN{\\c&H00FFFFFF&}."),
        ("0:01:13.00", "0:01:17.20", "When its route cuts across floodwater\\Npast our strict {\\c&H002020FF&}10% TOLERANCE{\\c&H00FFFFFF&},"),
        ("0:01:17.50", "0:01:21.80", "our {\\c&H0000E6FF&}LIANG-BARSKY GEOMETRY ENGINE{\\c&H00FFFFFF&}\\N{\\c&H002020FF&}INSTANTLY REJECTS IT WITH PROOF{\\c&H00FFFFFF&},"),
        ("0:01:22.00", "0:01:26.50", "forcing an autonomous {\\c&H0000E6FF&}SELF-CORRECTION LOOP{\\c&H00FFFFFF&}\\Nonto dry elevated asphalt."),
        ("0:01:26.80", "0:01:31.50", "{\\c&H0020FF00&}ZERO PERCENT HAZARD CONTACT{\\c&H00FFFFFF&}:\\N{\\c&H0020FF00&}CORRIDOR ONE VERIFIED{\\c&H00FFFFFF&}."),

        # --- ACT 4 (1:32 - 2:08) ---
        ("0:01:32.50", "0:01:36.50", "Only {\\c&H0020FF00&}MATHEMATICALLY VERIFIED{\\c&H00FFFFFF&} coordinates\\Nreach {\\c&H0000E6FF&}MUSE-WONDER-1.0{\\c&H00FFFFFF&}"),
        ("0:01:36.80", "0:01:40.50", "for {\\c&H0000E6FF&}HIGH-EFFORT TACTICAL DISPATCH{\\c&H00FFFFFF&}."),
        ("0:01:40.80", "0:01:44.80", "A strict Python guardrail {\\c&H002020FF&}HOLDS ANY UNIT{\\c&H00FFFFFF&}\\Ntargeted at an unverified zone."),
        ("0:01:45.00", "0:01:49.50", "Wonder synthesizes a {\\c&H0000E6FF&}5-UNIT ALLOCATION{\\c&H00FFFFFF&}:\\N{\\c&H0020FF00&}DRONES · RESCUE BOATS · MEDICAL{\\c&H00FFFFFF&}."),
        ("0:01:49.80", "0:01:54.20", "Alongside, {\\c&H0000E6FF&}MUSE-IMAGE-1.0{\\c&H00FFFFFF&} renders an official\\N{\\c&H0020FF00&}TACTICAL BRIEFING CARD{\\c&H00FFFFFF&}"),
        ("0:01:54.50", "0:01:59.00", "generated strictly from {\\c&H0020FF00&}VERIFIED FACTS ONLY{\\c&H00FFFFFF&},"),
        ("0:01:59.20", "0:02:05.50", "and one click exports the complete\\N{\\c&H0020FF00&}FEMA INCIDENT ACTION PLAN{\\c&H00FFFFFF&}."),

        # --- ACT 5 (2:08 - 2:42) ---
        ("0:02:08.00", "0:02:11.80", "To handle cascading crises,\\NCrisisGrid streams {\\c&H0000E6FF&}LIVE EARTHQUAKES{\\c&H00FFFFFF&}"),
        ("0:02:12.00", "0:02:16.00", "directly from the {\\c&H0000E6FF&}USGS SEISMIC FEED{\\c&H00FFFFFF&}."),
        ("0:02:16.20", "0:02:20.50", "Dispatchers select real epicenters to query\\n{\\c&H0020FF00&}HOSPITALS & SHELTERS VIA OSM{\\c&H00FFFFFF&}."),
        ("0:02:20.80", "0:02:25.00", "Finally, our {\\c&H0000E6FF&}CLEARANCE DELTA ENGINE{\\c&H00FFFFFF&}\\nmonitors post-engineering scenes,"),
        ("0:02:25.20", "0:02:29.80", "re-scanning {\\c&H0020FF00&}CLEARED BRIDGES{\\c&H00FFFFFF&}\\nand flipping their status from {\\c&H002020FF&}BLOCKED{\\c&H00FFFFFF&} to {\\c&H0020FF00&}GREEN{\\c&H00FFFFFF&}"),
        ("0:02:30.00", "0:02:34.50", "ONLY when physical geometry verifies safe passage."),
        ("0:02:34.80", "0:02:37.80", "{\\c&H0000E6FF&}5 META FRONTIER MODELS{\\c&H00FFFFFF&}."),
        ("0:02:38.00", "0:02:40.20", "{\\c&H0000E6FF&}1 API KEY{\\c&H00FFFFFF&}."),
        ("0:02:40.40", "0:02:42.00", "{\\c&H0020FF00&}ZERO UNVERIFIED GUESSES{\\c&H00FFFFFF&}.")
    ]

    for start, end, text in speech_lines:
        events.append(f"Dialogue: 1,{start},{end},Subtitle,,0,0,0,,{text}")

    ass_out = "docs/CrisisGrid_Tactical_Subtitles.ass"
    with open(ass_out, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

    print(f"  -> Generated complete HUD + Subtitle ASS file: {ass_out} ({len(events)} events)")
    return ass_out

if __name__ == "__main__":
    build_complete_ass()
