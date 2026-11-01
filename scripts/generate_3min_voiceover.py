import os
import sys
import time
import subprocess
import json

def generate_voiceover():
    print("=" * 70, flush=True)
    print("CRISISGRID — 3-MINUTE DEMO MASTER VOICEOVER GENERATOR (GEMINI 3.8 FLASH TTS)", flush=True)
    print("=" * 70, flush=True)

    valid_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY"))
    os.environ["GOOGLE_API_KEY"] = valid_key
    os.environ["GEMINI_API_KEY"] = valid_key

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=valid_key)

    out_dir = "demo_3min/voice"
    os.makedirs(out_dir, exist_ok=True)

    # 5 Acts tailored specifically for the 3-minute demo video (~165s total)
    acts = [
        {
            "id": "act1_intro_hook",
            "voice": "Puck",
            "text": (
                "When natural disasters strike anywhere in the world, emergency operations centers "
                "lose forty-five critical minutes manually cross-referencing aerial drone footage, "
                "chaotic radio chatter, and static maps. Worse, off-the-shelf vision models routinely "
                "hallucinate safe evacuation routes straight through twelve feet of raging floodwater. "
                "CrisisGrid is an autonomous multimodal disaster triage and emergency dispatch agent "
                "built on five Meta frontier models. Neural models propose; pure deterministic Python mathematics disposes."
            )
        },
        {
            "id": "act2_sam_and_voice",
            "voice": "Puck",
            "text": (
                "In one click, CrisisGrid launches nine parallel sam three point one segmentation calls, "
                "separating passable infrastructure like roads and bridges from critical hazards like floodwater, "
                "debris, and damaged buildings in just five seconds. Simultaneously, muse-voice-transcribe-one-point-zero "
                "processes incoming responder radio audio, decoding the field unit's mayday transmission directly "
                "into structured text with over ninety-nine percent accuracy."
            )
        },
        {
            "id": "act3_triage_and_reroute",
            "voice": "Puck",
            "text": (
                "Next, muse-spark-one-point-three fuses the radio call with the segmented aerial imagery to evaluate "
                "damage severity and propose candidate evacuation corridors. Notice that Spark proposes in dashed yellow, "
                "unverified by design. When its initial proposed route cuts across segmented floodwater past our strict "
                "ten percent tolerance, our deterministic Liang-Barsky geometry engine instantly rejects it with mathematical proof, "
                "forcing an autonomous self-correction loop onto dry elevated asphalt. "
                "Zero percent hazard contact: Corridor One verified."
            )
        },
        {
            "id": "act4_wonder_dispatch",
            "voice": "Puck",
            "text": (
                "Only mathematically verified coordinates are allowed to reach muse-wonder-one-point-zero for "
                "high-effort tactical dispatch reasoning. A strict Python guardrail holds back any rescue unit targeted "
                "at an unverified zone. Wonder synthesizes a comprehensive five-unit multi-agency allocation: aerial drone scouts, "
                "swift-water boats, and medical staging. Alongside, muse-image-one-point-zero renders an official tactical "
                "briefing card from verified facts only, and one click exports the complete FEMA Incident Action Plan."
            )
        },
        {
            "id": "act5_usgs_clearance_outro",
            "voice": "Puck",
            "text": (
                "To handle cascading crises, CrisisGrid streams live global earthquakes directly from the USGS seismic feed. "
                "Dispatchers can select real epicenters to query nearby hospitals and shelters via OpenStreetMap. "
                "Finally, our clearance delta engine monitors post-engineering scenes, re-scanning cleared bridges and flipping "
                "their status from blocked to green only when new physical geometry verifies safe passage. "
                "Five Meta frontier models. One API key. Zero unverified guesses."
            )
        }
    ]

    for idx, act in enumerate(acts):
        wav_path = os.path.join(out_dir, f"{act['id']}.wav")
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 10000:
            print(f"[{idx+1}/{len(acts)}] {act['id']} already exists, skipping.", flush=True)
            continue

        print(f"[{idx+1}/{len(acts)}] Generating '{act['id']}' with gemini-3.8-flash-tts...", flush=True)
        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model="gemini-3.8-flash-tts",
                    contents=act["text"],
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=act["voice"]
                                )
                            )
                        )
                    )
                )

                audio_data = None
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        audio_data = part.inline_data.data
                        break

                if audio_data:
                    with open(wav_path, "wb") as f:
                        f.write(audio_data)
                    print(f"  -> Saved {wav_path} ({len(audio_data)} bytes)", flush=True)
                    time.sleep(22)  # Respect free tier rate limit
                    break
                else:
                    print(f"  -> No audio data, retrying...", flush=True)
                    time.sleep(10)
            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    print(f"  -> Rate limit hit, sleeping 35s (attempt {attempt+1}/{max_retries})...", flush=True)
                    time.sleep(35)
                else:
                    print(f"  -> Error: {e}, retrying in 12s...", flush=True)
                    time.sleep(12)

    # Check and print audio durations
    print("\n" + "=" * 70, flush=True)
    print("AUDIO TRACK DURATIONS:", flush=True)
    total_dur = 0.0
    for act in acts:
        wav_path = os.path.join(out_dir, f"{act['id']}.wav")
        if os.path.exists(wav_path):
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", wav_path]
            out = json.loads(subprocess.check_output(cmd).decode())
            dur = float(out["format"]["duration"])
            total_dur += dur
            print(f"  • {act['id']}: {dur:.2f}s", flush=True)
    print(f"Total Spoken Voiceover Duration: {total_dur:.2f}s (~{total_dur/60:.2f} minutes)", flush=True)
    print("=" * 70, flush=True)

if __name__ == "__main__":
    generate_voiceover()

