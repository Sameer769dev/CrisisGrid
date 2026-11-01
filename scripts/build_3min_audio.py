import os
import subprocess
import numpy as np
import scipy.io.wavfile as wav

def get_speech_rms(audio):
    mono = np.mean(audio, axis=1) if audio.ndim > 1 else audio
    active = mono[np.abs(mono) > 0.02]
    if len(active) == 0:
        active = mono
    return np.sqrt(np.mean(active**2) + 1e-12)

def build_fixed_audio():
    print("=" * 70, flush=True)
    print("CRISISGRID — BROADCAST-CALIBRATED 3-MINUTE AUDIO MASTERING ENGINE", flush=True)
    print("=" * 70, flush=True)

    sr = 44100
    total_dur_s = 162.0
    total_samples = int(sr * total_dur_s)
    voice_dir = "demo_3min/voice"
    sfx_dir = "demo_3min/sfx"

    acts = [
        ("act1_intro_hook", 0.8),
        ("act2_sam_and_voice", 33.0),
        ("act3_triage_and_reroute", 60.0),
        ("act4_wonder_dispatch", 92.0),
        ("act5_usgs_clearance_outro", 128.0)
    ]

    # Step 1: Resample each raw act to 44.1kHz stereo via ffmpeg
    for act_name, _ in acts:
        in_f = f"{voice_dir}/{act_name}.wav"
        out_f = f"{voice_dir}/{act_name}_44k.wav"
        cmd = ["ffmpeg", "-y", "-i", in_f, "-ar", str(sr), "-ac", "2", out_f]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 2: Target active speech RMS for uniform loudness across all 5 acts
    target_speech_rms = 0.16  # ~ -16 dBFS speech energy
    master_voice = np.zeros((total_samples, 2), dtype=np.float32)

    print("Balancing and assembling voiceover acts on timeline...", flush=True)
    for act_name, start_sec in acts:
        wav_path = f"{voice_dir}/{act_name}_44k.wav"
        cur_sr, data = wav.read(wav_path)
        data = data.astype(np.float32) / 32768.0

        current_rms = get_speech_rms(data)
        gain = target_speech_rms / current_rms
        scaled_data = data * gain

        # Peak limiter per act to prevent any digital overs
        peak = np.max(np.abs(scaled_data))
        if peak > 0.92:
            scaled_data = scaled_data * (0.92 / peak)

        start_idx = int(sr * start_sec)
        end_idx = min(total_samples, start_idx + len(scaled_data))
        copy_len = end_idx - start_idx
        master_voice[start_idx:end_idx] = scaled_data[:copy_len]

        chunk_rms_db = 20 * np.log10(get_speech_rms(scaled_data))
        chunk_peak_db = 20 * np.log10(np.max(np.abs(scaled_data)))
        print(f"  * {act_name} @ {start_sec:5.1f}s: RMS = {chunk_rms_db:5.1f} dBFS, Peak = {chunk_peak_db:5.1f} dBFS", flush=True)

    temp_voice_raw = "demo_3min/temp_voice_raw.wav"
    wav.write(temp_voice_raw, sr, (master_voice * 32767).astype(np.int16))

    # Step 3: Broadcast EBU R128 loudness normalization on pure voiceover stem
    print("Normalizing master voiceover stem to EBU R128 standard (-16 LUFS, -1.5 dB True Peak)...", flush=True)
    cmd_voice_norm = [
        "ffmpeg", "-y",
        "-i", temp_voice_raw,
        "-af", "loudnorm=I=-16.0:TP=-1.5:LRA=7.0",
        "-ar", str(sr),
        "-c:a", "pcm_s16le",
        "docs/CrisisGrid_3Min_Master_Voiceover.wav"
    ]
    subprocess.check_call(cmd_voice_norm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("  -> Saved docs/CrisisGrid_3Min_Master_Voiceover.wav", flush=True)

    # Step 4: Build gentle ambient bed (warm analog sub-bass drone + radar pulse, -30 dB)
    t = np.linspace(0, total_dur_s, total_samples, endpoint=False)
    drone = 0.025 * np.sin(2 * np.pi * 55.0 * t) + 0.015 * np.sin(2 * np.pi * 82.4 * t)
    pulse = (np.sin(2 * np.pi * (1.0 / 2.0) * t) ** 16) * 0.015 * np.sin(2 * np.pi * 65.0 * t)
    fade_in = np.minimum(1.0, t / 3.0)
    fade_out = np.minimum(1.0, (total_dur_s - t) / 3.0)
    ambient_bed = np.column_stack([drone + pulse, drone + pulse]) * fade_in[:, None] * fade_out[:, None]

    # Step 5: Build SFX track on exact cue timestamps
    sfx_track = np.zeros((total_samples, 2), dtype=np.float32)
    sfx_cues = [
        ("chirp.wav", 33.5, 0.25),
        ("chirp.wav", 38.0, 0.25),
        ("warning.wav", 72.0, 0.35),
        ("chime.wav", 83.0, 0.35),
        ("click.wav", 110.0, 0.30),
        ("chime.wav", 146.0, 0.35),
    ]
    for sfx_name, cue_sec, sfx_vol in sfx_cues:
        sfx_path = f"{sfx_dir}/{sfx_name}"
        if os.path.exists(sfx_path):
            s_sr, s_data = wav.read(sfx_path)
            s_data = s_data.astype(np.float32) / 32768.0
            if s_data.ndim == 1:
                s_data = np.column_stack([s_data, s_data])
            # Resample if needed
            if s_sr != sr:
                # simple linear resample
                indices = np.linspace(0, len(s_data) - 1, int(len(s_data) * sr / s_sr)).astype(int)
                s_data = s_data[indices]
            s_data = s_data * sfx_vol
            st_idx = int(sr * cue_sec)
            en_idx = min(total_samples, st_idx + len(s_data))
            sfx_track[st_idx:en_idx] += s_data[:en_idx - st_idx]

    # Step 6: Direct Linear Mix (Voice 100% full clarity + subtle ambient bed + crisp SFX)
    master_mix_raw = master_voice + ambient_bed + sfx_track
    peak_mix = np.max(np.abs(master_mix_raw))
    if peak_mix > 0.95:
        master_mix_raw = master_mix_raw * (0.95 / peak_mix)

    temp_mix_raw = "demo_3min/temp_mix_raw.wav"
    wav.write(temp_mix_raw, sr, (master_mix_raw * 32767).astype(np.int16))

    # Step 7: Broadcast EBU R128 loudness normalization on final master mix
    print("Normalizing master mixed track to EBU R128 standard (-16 LUFS, -1.5 dB True Peak)...", flush=True)
    cmd_mix_norm = [
        "ffmpeg", "-y",
        "-i", temp_mix_raw,
        "-af", "loudnorm=I=-16.0:TP=-1.5:LRA=7.0",
        "-ar", str(sr),
        "-c:a", "pcm_s16le",
        "docs/CrisisGrid_3Min_Master_Audio_Mixed.wav"
    ]
    subprocess.check_call(cmd_mix_norm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("  -> Saved docs/CrisisGrid_3Min_Master_Audio_Mixed.wav", flush=True)

    # Step 8: Clean up temporary files
    for tmp in [temp_voice_raw, temp_mix_raw]:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

    # Step 9: Re-mux video with newly calibrated audio
    clean_mp4 = "docs/CrisisGrid_3Min_Clean_Screen_Recording.mp4"
    complete_mp4 = "docs/CrisisGrid_3Min_Complete_Demo.mp4"
    audio_mixed = "docs/CrisisGrid_3Min_Master_Audio_Mixed.wav"

    if os.path.exists(clean_mp4):
        print(f"Remuxing clean video with calibrated audio into {complete_mp4}...", flush=True)
        cmd_mux = [
            "ffmpeg", "-y",
            "-i", clean_mp4,
            "-i", audio_mixed,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "256k",
            "-shortest",
            complete_mp4
        ]
        subprocess.check_call(cmd_mux, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  -> Generated {complete_mp4} ({os.path.getsize(complete_mp4)/1024/1024:.2f} MB)", flush=True)

    print("\n=" * 70, flush=True)
    print("VALIDATING UNIFORM LOUDNESS ACROSS 10-SECOND TIME BLOCKS", flush=True)
    print("=" * 70, flush=True)

    def verify_loudness(path):
        v_sr, v_data = wav.read(path)
        if v_data.ndim > 1:
            v_data = v_data.mean(axis=1)
        v_data = v_data.astype(np.float32) / 32768.0
        block_size = v_sr * 10
        print(f"\nTimeline Loudness Analysis: {path}")
        for i in range(0, len(v_data), block_size):
            chunk = v_data[i:i + block_size]
            rms = np.sqrt(np.mean(chunk**2) + 1e-12)
            rms_db = 20 * np.log10(rms + 1e-12)
            peak_db = 20 * np.log10(np.max(np.abs(chunk)) + 1e-12)
            t_st = i / v_sr
            t_en = min(len(v_data), i + block_size) / v_sr
            print(f"  {t_st:5.1f}s - {t_en:5.1f}s: RMS = {rms_db:6.1f} dBFS | Peak = {peak_db:6.1f} dBFS")

    verify_loudness("docs/CrisisGrid_3Min_Master_Voiceover.wav")
    verify_loudness("docs/CrisisGrid_3Min_Master_Audio_Mixed.wav")

if __name__ == "__main__":
    build_fixed_audio()
