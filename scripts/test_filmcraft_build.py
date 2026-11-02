import subprocess
import json
import os

cli_path = r"C:\Program Files\ArtCraft\FilmCraft\filmcraft-cli.exe"
proj_path = r"C:\Users\dhana\Desktop\CrisisGrid\docs\CrisisGrid_Cinematic_Demo.fcproj"
docs_dir = r"C:\Users\dhana\Desktop\CrisisGrid\docs"

# 1. Create new project and import all media
media_filenames = [
    "CrisisGrid_3Min_Clean_Screen_Recording.mp4",
    "CrisisGrid_3Min_Master_Voiceover.wav",
    "Minimal Sub-Bass & Ticking Edit with Driving Percussion and Arpeggio.wav",
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

# Create fresh project
if os.path.exists(proj_path):
    os.remove(proj_path)

cmd_import = [cli_path, "--save-as", proj_path, "import"] + media_files
print("Importing media into FilmCraft project...")
res = subprocess.run(cmd_import, capture_output=True, text=True)
print("Import output:", res.stdout[:300])

# Inspect project items to map filename -> item ID
cmd_inspect = [cli_path, "--project", proj_path, "inspect", "project"]
res = subprocess.run(cmd_inspect, capture_output=True, text=True)
inspect_data = json.loads(res.stdout)

item_map = {}
def walk_children(node):
    if isinstance(node, dict):
        if "item" in node and "name" in node:
            item_map[node["name"]] = node["item"]
        if "children" in node:
            for c in node["children"]:
                walk_children(c)

walk_children(inspect_data["project"]["root"])
print("Mapped items:")
for k, v in item_map.items():
    print(f"  {k} -> ID {v}")
