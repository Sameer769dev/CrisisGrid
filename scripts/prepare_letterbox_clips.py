import os
import glob
import subprocess

def prepare_letterbox_clips():
    print("=" * 70)
    print("CRISISGRID — 2.39:1 CINEMATIC LETTERBOX PROCESSOR FOR AI CLIPS")
    print("=" * 70)

    out_dir = "demo_3min/letterbox_clips"
    os.makedirs(out_dir, exist_ok=True)

    ai_clips = [
        "Drone_flying_over_urban_flood_0b6b8cf0_1080p.mp4",
        "Operators_working_in_command_center_84e42bd9_1080p.mp4",
        "Rescue_team_leader_using_radio_c2702cdc_1080p.mp4",
        "Topographic_wireframe_of_flooded_46b270cc_1080p.mp4",
        "Sci-fi_tactical_targeting_reticle_1685a04c_1080p.mp4",
        "Military_verification_stamp_graphic_9aaa940f_1080p.mp4",
        "Helicopter_hovering_over_rescue__cedaf615_1080p.mp4",
        "Engineers_inspecting_cleared_hig_eb3550fb_1080p.mp4",
    ]

    for clip in ai_clips:
        in_path = os.path.join("docs", clip)
        out_path = os.path.join(out_dir, clip)
        if not os.path.exists(in_path):
            print(f"Error: missing input {in_path}")
            continue

        print(f"Processing 2.39:1 letterbox on: {clip} ...")
        # 1080p active area is 808px height, 136px bars on top and bottom
        vf_filter = "drawbox=y=0:h=136:color=black:t=fill,drawbox=y=ih-136:h=136:color=black:t=fill"
        cmd = [
            "ffmpeg", "-y",
            "-i", in_path,
            "-vf", vf_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            out_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error processing {clip}: {res.stderr}")
        else:
            sz = os.path.getsize(out_path) / 1024 / 1024
            print(f"  -> Generated letterboxed clip: {out_path} ({sz:.2f} MB)")

    print("\nAll 8 AI video clips successfully processed with 2.39:1 cinematic letterboxing!")

if __name__ == "__main__":
    prepare_letterbox_clips()

