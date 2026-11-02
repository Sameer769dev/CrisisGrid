import os
import subprocess
import numpy as np
import scipy.io.wavfile as wav

def load_wav_as_float(path, target_sr=48000):
    """Load audio file via ffmpeg resampled to target_sr stereo float32."""
    temp_wav = path + ".tmp.wav"
    cmd = [
        "ffmpeg", "-y", "-i", path,
        "-ar", str(target_sr),
        "-ac", "2",
        "-f", "wav",
        temp_wav
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg decode failed for {path}: {res.stderr}")
    sr, data = wav.read(temp_wav)
    if os.path.exists(temp_wav):
        os.remove(temp_wav)
    
    # Convert int16 or int32 or float to float32 in [-1.0, 1.0]
    if data.dtype == np.int16:
        float_data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        float_data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.float32:
        float_data = data
    else:
        float_data = data.astype(np.float32)
    return sr, float_data

def apply_fades(audio, sr, fade_in_s=0.0, fade_out_s=0.0):
    out = audio.copy()
    if fade_in_s > 0:
        n_in = int(fade_in_s * sr)
        if n_in > len(out): n_in = len(out)
        ramp = np.linspace(0.0, 1.0, n_in)[:, None]
        out[:n_in] *= ramp
    if fade_out_s > 0:
        n_out = int(fade_out_s * sr)
        if n_out > len(out): n_out = len(out)
        ramp = np.linspace(1.0, 0.0, n_out)[:, None]
        out[-n_out:] *= ramp
    return out

def build_dynamic_audio():
    print("=" * 70)
    print("CRISISGRID — BUILDING DYNAMIC MULTI-MOVEMENT MASTER AUDIO")
    print("=" * 70)

    sr = 48000
    duration_s = 162.0  # Exactly 2m 42s
    total_samples = int(duration_s * sr)

    # Master buffers
    voice_track = np.zeros((total_samples, 2), dtype=np.float32)
    music_track = np.zeros((total_samples, 2), dtype=np.float32)
    foley_track = np.zeros((total_samples, 2), dtype=np.float32)
    sfx_track   = np.zeros((total_samples, 2), dtype=np.float32)

    # 1. Voiceover Lead Track
    vo_path = "docs/CrisisGrid_3Min_Master_Voiceover.wav"
    print(f"Loading Master Voiceover: {vo_path}")
    _, vo_data = load_wav_as_float(vo_path, sr)
    n_vo = min(len(vo_data), total_samples)
    voice_track[:n_vo] = vo_data[:n_vo]

    # 2. Dynamic 3-Movement Score
    # Movement 1: Minimal Sub-Bass & Ticking Edit (0:00 - 33.5s)
    m1_path = "docs/Minimal Sub-Bass & Ticking Edit.wav"
    print(f"Loading Movement 1 (Tension / Hook): {m1_path}")
    _, m1_data = load_wav_as_float(m1_path, sr)
    # Cut 0:00 - 33.5s
    m1_samples = int(33.5 * sr)
    m1_cut = m1_data[:m1_samples]
    m1_cut = apply_fades(m1_cut, sr, fade_in_s=0.5, fade_out_s=1.5)
    # Volume: -19 dB
    vol_m1 = 10.0 ** (-19.0 / 20.0)
    music_track[:len(m1_cut)] += m1_cut * vol_m1

    # Movement 2: Dark Hybrid Cinematic Score (32.5s - 128.5s)
    m2_path = "docs/Dark Hybrid Cinematic Score (Take 1).wav"
    print(f"Loading Movement 2 (Action / AI Pipeline): {m2_path}")
    _, m2_data = load_wav_as_float(m2_path, sr)
    m2_start_sample = int(32.5 * sr)
    m2_dur_samples = int((128.5 - 32.5) * sr)
    m2_cut = m2_data[:m2_dur_samples]
    m2_cut = apply_fades(m2_cut, sr, fade_in_s=1.5, fade_out_s=1.5)
    # Volume: -18 dB
    vol_m2 = 10.0 ** (-18.0 / 20.0)
    music_track[m2_start_sample:m2_start_sample+len(m2_cut)] += m2_cut * vol_m2

    # Movement 3: Uplifting Triumphant Resolution (127.5s - 162.0s)
    m3_path = "docs/Uplifting Triumphant Resolution.wav"
    print(f"Loading Movement 3 (Triumph / Resolution): {m3_path}")
    _, m3_data = load_wav_as_float(m3_path, sr)
    m3_start_sample = int(127.5 * sr)
    m3_dur_samples = int((162.0 - 127.5) * sr)
    m3_cut = m3_data[:m3_dur_samples]
    m3_cut = apply_fades(m3_cut, sr, fade_in_s=1.5, fade_out_s=2.0)
    # Volume: -17 dB
    vol_m3 = 10.0 ** (-17.0 / 20.0)
    music_track[m3_start_sample:m3_start_sample+len(m3_cut)] += m3_cut * vol_m3

    # 3. AI Video Foley Sounds (from the 8 cutaway clips)
    ai_cutaways = [
        # (clip_name, start_time, duration, vol_db, fade_in, fade_out)
        ("Drone_flying_over_urban_flood_0b6b8cf0_1080p.mp4", 0.0, 6.5, -15.0, 0.3, 0.5),
        ("Operators_working_in_command_center_84e42bd9_1080p.mp4", 7.5, 5.0, -17.0, 0.3, 0.3),
        ("Rescue_team_leader_using_radio_c2702cdc_1080p.mp4", 44.0, 7.5, -16.0, 0.3, 0.3),
        ("Topographic_wireframe_of_flooded_46b270cc_1080p.mp4", 62.0, 6.5, -16.0, 0.3, 0.3),
        ("Sci-fi_tactical_targeting_reticle_1685a04c_1080p.mp4", 71.5, 5.5, -16.0, 0.3, 0.3),
        ("Military_verification_stamp_graphic_9aaa940f_1080p.mp4", 80.0, 5.0, -14.0, 0.2, 0.3),
        ("Helicopter_hovering_over_rescue__cedaf615_1080p.mp4", 98.5, 7.5, -15.0, 0.4, 0.5),
        ("Engineers_inspecting_cleared_hig_eb3550fb_1080p.mp4", 142.5, 7.0, -16.0, 0.3, 0.4),
    ]

    print("\nExtracting and placing AI Video Foley tracks...")
    for clip, start_t, dur_t, vol_db, fin, fout in ai_cutaways:
        clip_path = os.path.join("docs", clip)
        _, clip_audio = load_wav_as_float(clip_path, sr)
        n_samples = int(dur_t * sr)
        audio_seg = clip_audio[:n_samples]
        audio_seg = apply_fades(audio_seg, sr, fade_in_s=fin, fade_out_s=fout)
        vol = 10.0 ** (vol_db / 20.0)
        start_samp = int(start_t * sr)
        end_samp = start_samp + len(audio_seg)
        if end_samp > total_samples:
            audio_seg = audio_seg[:total_samples - start_samp]
            end_samp = total_samples
        foley_track[start_samp:end_samp] += audio_seg * vol
        print(f"  * Foley {clip:55} @ {start_t:5.1f}s - {start_t+dur_t:5.1f}s ({vol_db} dB)")

    # 4. Tactical UI Sound Effects
    tactical_cues = [
        ("demo_3min/sfx/click.wav", 33.0, -10.0),    # Click Run Pipeline
        ("demo_3min/sfx/chirp.wav", 38.5, -12.0),    # SAM 3.1 finish
        ("demo_3min/sfx/chirp.wav", 49.0, -12.0),    # ASR finish
        ("demo_3min/sfx/warning.wav", 74.0, -9.0),   # Hazard collision detected
        ("demo_3min/sfx/chime.wav", 86.5, -10.0),    # Corridor 1 verified green
        ("demo_3min/sfx/chirp.wav", 96.0, -12.0),    # Wonder 1.0 dispatch units
        ("demo_3min/sfx/chime.wav", 113.0, -10.0),   # Tactical briefing card generated
        ("demo_3min/sfx/click.wav", 129.0, -10.0),   # USGS seismic query
        ("demo_3min/sfx/chime.wav", 148.0, -10.0),   # Bridge clearance delta verified
    ]

    print("\nPlacing Tactical UI Sound Effects...")
    for sfx_file, cue_t, vol_db in tactical_cues:
        if os.path.exists(sfx_file):
            _, sfx_data = load_wav_as_float(sfx_file, sr)
            vol = 10.0 ** (vol_db / 20.0)
            start_samp = int(cue_t * sr)
            end_samp = start_samp + len(sfx_data)
            if end_samp > total_samples:
                sfx_data = sfx_data[:total_samples - start_samp]
                end_samp = total_samples
            sfx_track[start_samp:end_samp] += sfx_data * vol
            print(f"  * SFX {sfx_file:25} @ {cue_t:5.1f}s ({vol_db} dB)")

    # 5. Composite Mix
    print("\nCompositing Voiceover (0 dB) + Music Bed (-18 dB) + AI Foley + Tactical UI SFX...")
    raw_mix = voice_track + music_track + foley_track + sfx_track

    # Save unnormalized intermediate
    inter_path = "demo_3min/raw_mix_temp.wav"
    # Clip to avoid int16 wrap before loudnorm
    peak = np.max(np.abs(raw_mix))
    if peak > 0.99:
        raw_mix /= (peak / 0.95)
    wav.write(inter_path, sr, (raw_mix * 32767.0).astype(np.int16))

    # 6. Apply EBU R128 Professional Loudness Normalization (-16 LUFS, True Peak -1.5 dBTP)
    final_wav = "docs/CrisisGrid_3Min_Master_Audio_Mixed.wav"
    print(f"\nNormalizing final master to EBU R128 broadcast standard (-16 LUFS): {final_wav} ...")
    cmd_norm = [
        "ffmpeg", "-y",
        "-i", inter_path,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar", "48000",
        final_wav
    ]
    res = subprocess.run(cmd_norm, capture_output=True, text=True)
    if res.returncode != 0:
        print("Loudnorm failed:", res.stderr)
        return False
    if os.path.exists(inter_path):
        os.remove(inter_path)

    sz_mb = os.path.getsize(final_wav) / 1024 / 1024
    print(f"\nSUCCESS! Master audio exported to {final_wav} ({sz_mb:.2f} MB, {duration_s:.1f}s)")
    return True

if __name__ == "__main__":
    build_dynamic_audio()

