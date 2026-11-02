import subprocess
import json
import os
import sys

def build_filmcraft_master():
    print("=" * 75)
    print("CRISISGRID — MULTI-TRACK FILMCRAFT CINEMATIC PROJECT BUILDER")
    print("=" * 75)

    cli_path = r"C:\Program Files\ArtCraft\FilmCraft\filmcraft-cli.exe"
    proj_path = r"C:\Users\dhana\Desktop\CrisisGrid\docs\CrisisGrid_Cinematic_Demo.fcproj"
    docs_dir = r"C:\Users\dhana\Desktop\CrisisGrid\docs"
    export_mp4 = r"C:\Users\dhana\Desktop\CrisisGrid\docs\CrisisGrid_3Min_Cinematic_Master_FilmCraft.mp4"
    srt_path = r"C:\Users\dhana\Desktop\CrisisGrid\docs\CrisisGrid_Tactical_Subtitles.srt"

    # All individual media assets
    media_filenames = [
        "CrisisGrid_3Min_Clean_Screen_Recording.mp4",
        "CrisisGrid_3Min_Master_Voiceover.wav",
        "Minimal Sub-Bass & Ticking Edit.wav",
        "Dark Hybrid Cinematic Score (Take 1).wav",
        "Uplifting Triumphant Resolution.wav",
        "Drone_flying_over_urban_flood_0b6b8cf0_1080p.mp4",
        "Operators_working_in_command_center_84e42bd9_1080p.mp4",
        "Rescue_team_leader_using_radio_c2702cdc_1080p.mp4",
        "Topographic_wireframe_of_flooded_46b270cc_1080p.mp4",
        "Sci-fi_tactical_targeting_reticle_1685a04c_1080p.mp4",
        "Military_verification_stamp_graphic_9aaa940f_1080p.mp4",
        "Helicopter_hovering_over_rescue__cedaf615_1080p.mp4",
        "Engineers_inspecting_cleared_hig_eb3550fb_1080p.mp4",
    ]
    media_files = [os.path.join(docs_dir, f) for f in media_filenames]

    for p in media_files:
        if not os.path.exists(p):
            print(f"Error: Missing media file: {p}")
            return False

    # 1. Initialize project with imported media
    print("\n[Step 1/6] Importing media files into FilmCraft project...")
    if os.path.exists(proj_path):
        os.remove(proj_path)

    cmd_import = [cli_path, "--save-as", proj_path, "import"] + media_files
    res = subprocess.run(cmd_import, capture_output=True, text=True)
    if res.returncode != 0:
        print("Import failed:", res.stderr)
        return False
    print(f"  -> {len(media_files)} individual media assets imported successfully into FilmCraft.")

    # 2. Inspect project to map filename -> item ID
    cmd_inspect = [cli_path, "--project", proj_path, "inspect", "project"]
    res = subprocess.run(cmd_inspect, capture_output=True, text=True)
    inspect_data = json.loads(res.stdout)

    item_map = {}
    for c in inspect_data["root"]["children"]:
        item_map[c["name"]] = c["item"]

    print("\n[Step 2/6] Asset Item ID Mappings:")
    for name, iid in item_map.items():
        print(f"  * {name:60} : Item {iid}")

    # 3. Create Multi-Track Sequence
    print("\n[Step 3/6] Creating Multi-Track Sequence (3 Video Tracks, 5 Audio Tracks)...")
    script_commands = [
        {
            "id": "file.newSequence",
            "params": {
                "name": "CrisisGrid - 3-Minute Cinematic Master",
                "width": 1920,
                "height": 1080,
                "fps": 30.0,
                "sampleRate": 48000,
                "video": 3,
                "audio": 5
            }
        },
        # --- VIDEO 1: Base Screen Recording (Full 16:9 UI) ---
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["CrisisGrid_3Min_Clean_Screen_Recording.mp4"],
                "track": "V1",
                "seconds": 0.0,
                "duration": {"seconds": 162.0},
                "video": True,
                "audio": False,
                "insert": False
            }
        },
        # --- AUDIO 1: Master Voiceover Lead Track (0 dB) ---
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["CrisisGrid_3Min_Master_Voiceover.wav"],
                "track": "A1",
                "seconds": 0.0,
                "duration": {"seconds": 162.0},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        # --- AUDIO 2: Movement 1 (Tension / Hook: 0:00 - 33.5s) ---
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Minimal Sub-Bass & Ticking Edit.wav"],
                "track": "A2",
                "seconds": 0.0,
                "duration": {"seconds": 33.5},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        {
            "id": "timeline.setTrack",
            "params": {"track": "A2", "volumeDb": -19.0}
        },
        # --- AUDIO 3: Movement 2 (Action Score: 32.5s - 128.5s) ---
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Dark Hybrid Cinematic Score (Take 1).wav"],
                "track": "A3",
                "seconds": 32.5,
                "duration": {"seconds": 96.0},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        {
            "id": "timeline.setTrack",
            "params": {"track": "A3", "volumeDb": -18.0}
        },
        # --- AUDIO 4: Movement 3 (Triumphant Resolution: 127.5s - 162.0s) ---
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Uplifting Triumphant Resolution.wav"],
                "track": "A4",
                "seconds": 127.5,
                "duration": {"seconds": 34.5},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        {
            "id": "timeline.setTrack",
            "params": {"track": "A4", "volumeDb": -17.0}
        },
        # Set Track A5 Volume for AI Foley
        {
            "id": "timeline.setTrack",
            "params": {"track": "A5", "volumeDb": -16.0}
        },
        # --- VIDEO 2 (Cutaways) & AUDIO 5 (Native Video Foley) ---
        # 1. Drone over urban flood (0:00 - 0:06.5)
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Drone_flying_over_urban_flood_0b6b8cf0_1080p.mp4"],
                "track": "V2",
                "seconds": 0.0,
                "duration": {"seconds": 6.5},
                "video": True,
                "audio": False,
                "insert": False
            }
        },
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Drone_flying_over_urban_flood_0b6b8cf0_1080p.mp4"],
                "track": "A5",
                "seconds": 0.0,
                "duration": {"seconds": 6.5},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        # 2. Command Center Operators (0:07.5 - 0:12.5)
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Operators_working_in_command_center_84e42bd9_1080p.mp4"],
                "track": "V2",
                "seconds": 7.5,
                "duration": {"seconds": 5.0},
                "video": True,
                "audio": False,
                "insert": False
            }
        },
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Operators_working_in_command_center_84e42bd9_1080p.mp4"],
                "track": "A5",
                "seconds": 7.5,
                "duration": {"seconds": 5.0},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        # 3. Rescue Team Leader Radio Mayday (0:44.0 - 0:51.5)
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Rescue_team_leader_using_radio_c2702cdc_1080p.mp4"],
                "track": "V2",
                "seconds": 44.0,
                "duration": {"seconds": 7.5},
                "video": True,
                "audio": False,
                "insert": False
            }
        },
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Rescue_team_leader_using_radio_c2702cdc_1080p.mp4"],
                "track": "A5",
                "seconds": 44.0,
                "duration": {"seconds": 7.5},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        # 4. Topographic Wireframe LiDAR Mesh (1:02.0 - 1:08.5)
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Topographic_wireframe_of_flooded_46b270cc_1080p.mp4"],
                "track": "V2",
                "seconds": 62.0,
                "duration": {"seconds": 6.5},
                "video": True,
                "audio": False,
                "insert": False
            }
        },
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Topographic_wireframe_of_flooded_46b270cc_1080p.mp4"],
                "track": "A5",
                "seconds": 62.0,
                "duration": {"seconds": 6.5},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        # 5. Sci-Fi Tactical Targeting Reticle (1:11.5 - 1:17.0)
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Sci-fi_tactical_targeting_reticle_1685a04c_1080p.mp4"],
                "track": "V2",
                "seconds": 71.5,
                "duration": {"seconds": 5.5},
                "video": True,
                "audio": False,
                "insert": False
            }
        },
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Sci-fi_tactical_targeting_reticle_1685a04c_1080p.mp4"],
                "track": "A5",
                "seconds": 71.5,
                "duration": {"seconds": 5.5},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        # 6. Military Verification Stamp (1:20.0 - 1:25.0)
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Military_verification_stamp_graphic_9aaa940f_1080p.mp4"],
                "track": "V2",
                "seconds": 80.0,
                "duration": {"seconds": 5.0},
                "video": True,
                "audio": False,
                "insert": False
            }
        },
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Military_verification_stamp_graphic_9aaa940f_1080p.mp4"],
                "track": "A5",
                "seconds": 80.0,
                "duration": {"seconds": 5.0},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        # 7. Military Helicopter & Swiftwater Boat (1:38.5 - 1:46.0)
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Helicopter_hovering_over_rescue__cedaf615_1080p.mp4"],
                "track": "V2",
                "seconds": 98.5,
                "duration": {"seconds": 7.5},
                "video": True,
                "audio": False,
                "insert": False
            }
        },
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Helicopter_hovering_over_rescue__cedaf615_1080p.mp4"],
                "track": "A5",
                "seconds": 98.5,
                "duration": {"seconds": 7.5},
                "video": False,
                "audio": True,
                "insert": False
            }
        },
        # 8. Post-Clearance Bridge Engineers (2:22.5 - 2:29.5)
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Engineers_inspecting_cleared_hig_eb3550fb_1080p.mp4"],
                "track": "V2",
                "seconds": 142.5,
                "duration": {"seconds": 7.0},
                "video": True,
                "audio": False,
                "insert": False
            }
        },
        {
            "id": "timeline.place",
            "params": {
                "item": item_map["Engineers_inspecting_cleared_hig_eb3550fb_1080p.mp4"],
                "track": "A5",
                "seconds": 142.5,
                "duration": {"seconds": 7.0},
                "video": False,
                "audio": True,
                "insert": False
            }
        }
    ]

    script_path = "scripts/filmcraft_sequence_script.jsonl"
    with open(script_path, "w", encoding="utf-8") as f:
        for cmd in script_commands:
            f.write(json.dumps(cmd) + "\n")

    print(f"Executing {len(script_commands)} timeline editing commands in FilmCraft...")
    cmd_run = [cli_path, "--project", proj_path, "--save", "run", script_path]
    res = subprocess.run(cmd_run, capture_output=True, text=True)
    if res.returncode != 0:
        print("Timeline script execution error:", res.stderr)
        return False
    print("  -> All 3 Video and 5 Audio tracks assembled and saved!")

    # 4. Apply cross_dissolve transitions to cutaways
    print("\n[Step 4/6] Applying cinematic cross-dissolves to cutaways on Video 2...")
    cmd_inspect_seq = [cli_path, "--project", proj_path, "inspect", "sequence"]
    res = subprocess.run(cmd_inspect_seq, capture_output=True, text=True)
    try:
        seq_data = json.loads(res.stdout)
        v2_clips = []
        for track in seq_data.get("video", []):
            if track.get("name") == "Video 2":
                for item in track.get("items", []):
                    v2_clips.append(item.get("clip"))
        print(f"  Found {len(v2_clips)} cutaway clips on Video 2: {v2_clips}")

        trans_cmds = []
        for cid in v2_clips:
            trans_cmds.append({
                "id": "sequence.applyVideoTransition",
                "params": {"clip": cid, "effect": "cross_dissolve", "frames": 14, "edge": "out"}
            })
            trans_cmds.append({
                "id": "sequence.applyVideoTransition",
                "params": {"clip": cid, "effect": "cross_dissolve", "frames": 14, "edge": "in"}
            })

        trans_script = "scripts/filmcraft_transitions.jsonl"
        with open(trans_script, "w", encoding="utf-8") as f:
            for tc in trans_cmds:
                f.write(json.dumps(tc) + "\n")

        subprocess.run([cli_path, "--project", proj_path, "--save", "run", trans_script], capture_output=True, text=True)
        print("  -> Cross-dissolves applied to all cutaways!")
    except Exception as e:
        print("  Notice on transitions:", e)

    # 5. Import and Style Caption Track (C1) in FilmCraft
    print("\n[Step 5/6] Importing Tactical Subtitle Track (C1) into FilmCraft...")
    cmd_cap = [
        cli_path, "--project", proj_path, "--save",
        "exec", "captions.import",
        f"path={srt_path.replace(os.sep, '/')}"
    ]
    res_cap = subprocess.run(cmd_cap, capture_output=True, text=True)
    print("  Captions import result:", res_cap.stdout.strip())

    # Set Caption Style to Impact 54pt
    style_params = json.dumps({
        "track": "C1",
        "font": "Impact",
        "size": 54.0,
        "color": "#ffffff",
        "outline": 4.5,
        "outlineColor": "#000000",
        "align": "center"
    })
    cmd_style = [
        cli_path, "--project", proj_path, "--save",
        "exec", "captions.setStyle",
        style_params
    ]
    res_style = subprocess.run(cmd_style, capture_output=True, text=True)
    print("  Captions style result:", res_style.stdout.strip())

    # 6. Export Master Video via FilmCraft Renderer
    print(f"\n[Step 6/6] Exporting master video via FilmCraft engine: {export_mp4} ...")
    cmd_export = [
        cli_path,
        "--project", proj_path,
        "export", export_mp4,
        "--preset", "YouTube 1080p Full HD"
    ]
    res = subprocess.run(cmd_export, capture_output=True, text=True)
    if res.returncode != 0:
        print("Export error:", res.stderr)
        return False
    
    print(f"Export result: {res.stdout.strip()}")
    if os.path.exists(export_mp4):
        size_mb = os.path.getsize(export_mp4) / 1024 / 1024
        print(f"\nSUCCESS! Multi-Track FilmCraft Master rendered: {export_mp4} ({size_mb:.2f} MB)")
        return True
    return False

if __name__ == "__main__":
    build_filmcraft_master()
