import os
import glob
import subprocess
import shutil

def finalize():
    print("=" * 70)
    print("CRISISGRID — FINALIZING 3-MINUTE DEMO DELIVERABLES")
    print("=" * 70)

    webms = glob.glob("demo_3min/raw_video/*.webm")
    if not webms:
        print("ERROR: No .webm video found in demo_3min/raw_video/")
        return False

    # Get newest webm
    latest_webm = max(webms, key=os.path.getmtime)
    print(f"Source video: {latest_webm} ({os.path.getsize(latest_webm) / 1024 / 1024:.2f} MB)")

    os.makedirs("docs", exist_ok=True)

    clean_mp4 = "docs/CrisisGrid_3Min_Clean_Screen_Recording.mp4"
    print(f"Transcoding clean recording to {clean_mp4} (1080p 30fps H.264)...")
    cmd_transcode = [
        "ffmpeg", "-y",
        "-i", latest_webm,
        "-vf", "fps=30",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        clean_mp4
    ]
    subprocess.run(cmd_transcode, check=True)
    print(f"Clean MP4 generated: {os.path.getsize(clean_mp4) / 1024 / 1024:.2f} MB")

    # Copy audio stems to docs/
    voiceover_stem_src = "demo_3min/master_voiceover_stem.wav"
    audio_mixed_src = "demo_3min/master_audio_mixed.wav"

    voiceover_dest = "docs/CrisisGrid_3Min_Master_Voiceover.wav"
    audio_mixed_dest = "docs/CrisisGrid_3Min_Master_Audio_Mixed.wav"

    shutil.copyfile(voiceover_stem_src, voiceover_dest)
    shutil.copyfile(audio_mixed_src, audio_mixed_dest)
    print(f"Copied voiceover stem to {voiceover_dest}")
    print(f"Copied master audio mixed to {audio_mixed_dest}")

    # Mux clean MP4 + mixed audio into Complete Demo MP4
    complete_mp4 = "docs/CrisisGrid_3Min_Complete_Demo.mp4"
    print(f"Muxing clean video + master audio into {complete_mp4}...")
    cmd_mux = [
        "ffmpeg", "-y",
        "-i", clean_mp4,
        "-i", audio_mixed_dest,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        "-shortest",
        complete_mp4
    ]
    subprocess.run(cmd_mux, check=True)
    print(f"Complete Demo MP4 generated: {os.path.getsize(complete_mp4) / 1024 / 1024:.2f} MB")

    # Inspect final durations via ffprobe
    for label, path in [
        ("Clean Screen MP4", clean_mp4),
        ("Complete Demo MP4", complete_mp4),
        ("Voiceover Stem", voiceover_dest),
        ("Master Audio Mixed", audio_mixed_dest)
    ]:
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
            out = subprocess.check_output(cmd).decode().strip()
            dur = float(out)
            mins = int(dur // 60)
            secs = dur % 60
            print(f"  * {label}: {mins}m {secs:04.1f}s ({dur:.2f}s) — {os.path.getsize(path)/1024/1024:.2f} MB")
        except Exception as e:
            print(f"  * {label}: size={os.path.getsize(path)/1024/1024:.2f} MB (error reading duration: {e})")

    print("\nAll deliverables are ready in docs/!")
    return True

if __name__ == "__main__":
    finalize()

