import subprocess
import os
import numpy as np
import scipy.io.wavfile as wav

def build_3min_audio():
    print("=" * 70, flush=True)
    print("CRISISGRID — 3-MINUTE AUDIO MASTER MIXER", flush=True)
    print("=" * 70, flush=True)

    os.makedirs("demo_3min", exist_ok=True)
    voice_dir = "demo_3min/voice"

    acts = [
        "act1_intro_hook",
        "act2_sam_and_voice",
        "act3_triage_and_reroute",
        "act4_wonder_dispatch",
        "act5_usgs_clearance_outro"
    ]
    for act in acts:
        in_f = f"{voice_dir}/{act}.wav"
        out_f = f"{voice_dir}/{act}_44k.wav"
        cmd = ["ffmpeg", "-y", "-i", in_f, "-ar", "44100", "-ac", "2", out_f]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    t_act1 = 500
    t_act2 = 33000
    t_act3 = 60000
    t_act4 = 92000
    t_act5 = 128000
    total_dur_s = 162.0

    # 1. Pure Voiceover Dialogue Stem
    filter_voice_only = (
        f"[0:a]adelay={t_act1}|{t_act1},volume=1.05[a1];"
        f"[1:a]adelay={t_act2}|{t_act2},volume=1.05[a2];"
        f"[2:a]adelay={t_act3}|{t_act3},volume=1.05[a3];"
        f"[3:a]adelay={t_act4}|{t_act4},volume=1.05[a4];"
        f"[4:a]adelay={t_act5}|{t_act5},volume=1.05[a5];"
        f"[a1][a2][a3][a4][a5]amix=inputs=5:duration=longest:dropout_transition=0,volume=1.0[outv]"
    )
    cmd_voice_only = [
        "ffmpeg", "-y",
        "-i", f"{voice_dir}/act1_intro_hook_44k.wav",
        "-i", f"{voice_dir}/act2_sam_and_voice_44k.wav",
        "-i", f"{voice_dir}/act3_triage_and_reroute_44k.wav",
        "-i", f"{voice_dir}/act4_wonder_dispatch_44k.wav",
        "-i", f"{voice_dir}/act5_usgs_clearance_outro_44k.wav",
        "-filter_complex", filter_voice_only,
        "-map", "[outv]",
        "-t", str(total_dur_s),
        "-c:a", "pcm_s16le",
        "demo_3min/master_voiceover_stem.wav"
    ]
    print("Generating pure voiceover dialogue stem...", flush=True)
    subprocess.check_call(cmd_voice_only)
    print("  -> Saved demo_3min/master_voiceover_stem.wav", flush=True)

    # 2. Ambient bed
    sr = 44100
    t = np.linspace(0, total_dur_s, int(sr * total_dur_s), endpoint=False)
    drone = 0.05 * np.sin(2 * np.pi * 55.0 * t) + 0.03 * np.sin(2 * np.pi * 82.4 * t)
    pulse = (np.sin(2 * np.pi * (1.0 / 2.0) * t) ** 16) * 0.025 * np.sin(2 * np.pi * 65.0 * t)
    bed = drone + pulse
    fade_in = np.minimum(1.0, t / 2.0)
    fade_out = np.minimum(1.0, (total_dur_s - t) / 2.5)
    bed = (bed * fade_in * fade_out * 32767).astype(np.int16)
    wav.write("demo_3min/ambient_bed.wav", sr, bed)

    # 3. Master Audio Mix with subtle SFX
    sfx_dir = "demo_3min/sfx"
    filter_master_mix = (
        f"[0:a]volume=0.35[ambient];"
        f"[1:a]volume=1.0[voice];"
        f"[2:a]adelay=33500|33500,volume=0.4[chirp1];"
        f"[2:a]adelay=38000|38000,volume=0.4[chirp2];"
        f"[3:a]adelay=72000|72000,volume=0.6[warn];"
        f"[4:a]adelay=83000|83000,volume=0.65[chime1];"
        f"[5:a]adelay=110000|110000,volume=0.5[click1];"
        f"[4:a]adelay=146000|146000,volume=0.65[chime2];"
        f"[ambient][voice][chirp1][chirp2][warn][chime1][click1][chime2]"
        f"amix=inputs=8:duration=longest:dropout_transition=0,volume=1.1[outm]"
    )
    cmd_master_mix = [
        "ffmpeg", "-y",
        "-i", "demo_3min/ambient_bed.wav",
        "-i", "demo_3min/master_voiceover_stem.wav",
        "-i", f"{sfx_dir}/chirp.wav",
        "-i", f"{sfx_dir}/warning.wav",
        "-i", f"{sfx_dir}/chime.wav",
        "-i", f"{sfx_dir}/click.wav",
        "-filter_complex", filter_master_mix,
        "-map", "[outm]",
        "-t", str(total_dur_s),
        "-c:a", "pcm_s16le",
        "demo_3min/master_audio_mixed.wav"
    ]
    print("Generating full mixed master audio track...", flush=True)
    subprocess.check_call(cmd_master_mix)
    print("  -> Saved demo_3min/master_audio_mixed.wav", flush=True)

    print("=" * 70, flush=True)
    print(f"AUDIO MASTERING COMPLETE! Runtime: {total_dur_s:.1f}s (2:42)", flush=True)
    print("=" * 70, flush=True)

if __name__ == "__main__":
    build_3min_audio()
