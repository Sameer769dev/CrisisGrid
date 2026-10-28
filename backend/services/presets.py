"""Day 8 (Nov 3, 2026): pre-loaded global disaster presets for 1-click
judge testing. Static, honest metadata - this module makes ZERO model
calls and contains NO pre-baked results: every preset still runs the live
Days 2-5 pipeline (sam-3.1 -> triage -> verifier -> dispatch) when a judge
clicks it. If segmentation finds nothing or nothing verifies, the normal
honest failure states apply.

Imagery provenance (declared, never hidden):
- urban-flood: demo frame already used for the Day 5 live proof
  (live-flood.jpg / live-flood-briefing-card.png at repo root).
- earthquake-bridge / wildfire-helipad: demo frames generated with
  muse-image-1.0 (the only permitted image model) purely as test scenes;
  all hazard claims about them come from live sam-3.1 at click time.
Coordinates are illustrative demo coordinates for the optional OSM
facility lookup; facility results are whatever Overpass returns live.
"""
from __future__ import annotations

from typing import Any

PRESETS: list[dict[str, Any]] = [
    {
        "id": "urban-flood",
        "name": "Urban Flood Corridor",
        "disaster_type": "flood",
        "day": 8,
        "description": "Flooded urban corridor: water over low roads, residents on rooftops, one possibly passable bridge. Find a verified evacuation corridor and a high-ground landing zone.",
        "image_path": "/presets/urban-flood.jpg",
        "image_filename": "urban-flood.jpg",
        "image_provenance": "Pre-loaded aerial flood demo frame (live-flood.jpg). Segmentation and geometric verification run live on click - nothing is pre-baked.",
        "audio_path": "/presets/field-radio.wav",
        "audio_filename": "field-radio.wav",
        "field_report": "Flood water across the low road and market area, residents stranded on rooftops, water still rising. Need boat rescue teams and a high-ground helicopter landing zone. The bridge on the east side may still be passable - please verify before sending vehicles.",
        "latitude": 27.7172, "longitude": 85.3240,
        "coordinates_note": "Illustrative demo coordinates (Kathmandu) for the optional OSM emergency-facility lookup.",
        "expected_focus": ["flood water", "road", "bridge", "rooftop", "stranded vehicle"],
        "judge_hint": "Watch the first Spark corridor get rejected if it crosses flood water, then re-routed and verified before Wonder dispatches.",
    },
    {
        "id": "earthquake-bridge",
        "name": "Earthquake Bridge & Rubble Triage",
        "disaster_type": "earthquake",
        "day": 8,
        "description": "Earthquake-damaged district: cracked, partly collapsed bridge, rubble-blocked streets, damaged buildings. Prioritise debris clearance, medical access and a flat landing zone.",
        "image_path": "/presets/earthquake-bridge.jpg",
        "image_filename": "earthquake-bridge.jpg",
        "image_provenance": "Synthetic tactical scenario generated with muse-image-1.0. All hazard claims come from live sam-3.1 segmentation at click time - the image itself asserts nothing.",
        "audio_path": None,
        "audio_filename": None,
        "field_report": "Strong earthquake has cracked the river bridge and dropped rubble across the main street. People are trapped in damaged buildings on both sides of the river. Need heavy debris clearance, medical teams, and a clear flat landing zone on undamaged ground.",
        "latitude": 38.4237, "longitude": 27.1428,
        "coordinates_note": "Illustrative demo coordinates (Izmir region) for the optional OSM emergency-facility lookup.",
        "expected_focus": ["debris", "damaged building", "bridge", "clear flat ground", "road"],
        "judge_hint": "Check whether the bridge segments as passable or damaged, and whether the verifier keeps corridors off the rubble.",
    },
    {
        "id": "wildfire-helipad",
        "name": "Wildfire Evacuation & Helipad Finder",
        "disaster_type": "wildfire",
        "day": 8,
        "description": "Wildfire front approaching a rural town: fire and scorched ground on the ridge, one winding evacuation road, open field for a helipad. Verify an evacuation corridor away from the fire line.",
        "image_path": "/presets/wildfire-helipad.jpg",
        "image_filename": "wildfire-helipad.jpg",
        "image_provenance": "Synthetic tactical scenario generated with muse-image-1.0. All hazard claims come from live sam-3.1 segmentation at click time - the image itself asserts nothing.",
        "audio_path": None,
        "audio_filename": None,
        "field_report": "Wildfire front is moving toward town from the forested ridge and smoke is crossing the west road. Residents need an evacuation route away from the fire line, and helicopters need a clear flat helipad on open ground well clear of the flames.",
        "latitude": 39.2000, "longitude": -120.9000,
        "coordinates_note": "Illustrative demo coordinates (Sierra Nevada foothills) for the optional OSM emergency-facility lookup.",
        "expected_focus": ["fire", "road", "clear flat ground", "rooftop", "debris"],
        "judge_hint": "The landing zone must clear the fire detections with real clearance area - watch the clearance numbers in the trace, not just the colour.",
    },
]


def list_presets() -> dict[str, Any]:
    return {
        "status": "ok", "day": 8, "engine": "static_metadata", "model_calls": 0,
        "count": len(PRESETS), "presets": PRESETS,
        "honesty_note": ("Presets bundle imagery + a field report only. Every hazard, corridor, "
                         "verification and dispatch result is produced live by the CrisisGrid pipeline "
                         "when the preset is run; a preset can honestly end in rejection or "
                         "completed_no_dispatch like any other input."),
        "next_step": "Load a preset in the frontend (Mission Control presets) or POST its image + field_report to /api/run-crisisgrid.",
    }


def get_preset(preset_id: str) -> dict[str, Any] | None:
    for preset in PRESETS:
        if preset["id"] == preset_id:
            return preset
    return None
