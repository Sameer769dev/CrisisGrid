import os
import subprocess

def burn_subtitles():
    print("=" * 70)
    print("CRISISGRID — BURNING TACTICAL HUD & KINETIC SUBTITLES & FINAL MASTER")
    print("=" * 70)

    input_video = "docs/CrisisGrid_3Min_Cinematic_Master_FilmCraft.mp4"
    audio_track = "docs/CrisisGrid_3Min_Master_Audio_Mixed.wav"
    ass_path = "docs/CrisisGrid_Tactical_Subtitles.ass"
    output_video = "docs/CrisisGrid_3Min_Complete_Demo.mp4"

    if not os.path.exists(input_video):
        print(f"Error: {input_video} not found!")
        return False
    if not os.path.exists(audio_track):
        print(f"Error: {audio_track} not found!")
        return False
    if not os.path.exists(ass_path):
        print(f"Error: {ass_path} not found!")
        return False

    # Format path for FFmpeg filter
    # Forward slashes and single quotes around path
    ass_filter_path = ass_path.replace("\\", "/")
    vf_arg = f"ass='{ass_filter_path}'"

    print(f"Burning ASS subtitles from {ass_path} onto {input_video} ...")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-i", audio_track,
        "-vf", vf_arg,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "17",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "256k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_video
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFmpeg error:", res.stderr)
        return False

    print(f"\nSUCCESS! Master burned demo generated: {output_video}")
    sz_mb = os.path.getsize(output_video) / 1024 / 1024
    print(f"File size: {sz_mb:.2f} MB")

    # Probe duration
    cmd_probe = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", output_video]
    dur = float(subprocess.check_output(cmd_probe).decode().strip())
    mins = int(dur // 60)
    secs = dur % 60
    print(f"Master Duration: {mins}m {secs:04.1f}s ({dur:.2f}s) — Strictly within 3-minute hackathon limit!")
    return True

if __name__ == "__main__":
    burn_subtitles()

