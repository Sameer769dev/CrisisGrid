// Day 8 preset metadata - mirrors GET /api/presets (backend/services/presets.py).
// Used as instant fallback if the backend is unreachable; the page refreshes
// from the API when available. Presets carry imagery + report ONLY - every
// result is produced live by the pipeline. Keep ids in sync with the backend.
export interface CrisisPreset {
  id: string; name: string; disaster_type: string;
  description: string; image_path: string; image_filename: string;
  image_provenance: string; audio_path: string | null; audio_filename: string | null;
  field_report: string; latitude: number | null; longitude: number | null;
  coordinates_note?: string; expected_focus: string[]; judge_hint: string;
}

export const FALLBACK_PRESETS: CrisisPreset[] = [
  {
    id: "urban-flood", name: "Urban Flood Corridor", disaster_type: "flood",
    description: "Flooded urban corridor: water over low roads, residents on rooftops, one possibly passable bridge. Find a verified evacuation corridor and a high-ground landing zone.",
    image_path: "/presets/urban-flood.jpg", image_filename: "urban-flood.jpg",
    image_provenance: "Pre-loaded demo frame (Day 5 live-proof scene). Segmentation runs live on click.",
    audio_path: "/presets/field-radio.wav", audio_filename: "field-radio.wav",
    field_report: "Flood water across the low road and market area, residents stranded on rooftops, water still rising. Need boat rescue teams and a high-ground helicopter landing zone. The bridge on the east side may still be passable - please verify before sending vehicles.",
    latitude: 27.7172, longitude: 85.3240,
    expected_focus: ["flood water", "road", "bridge", "rooftop", "stranded vehicle"],
    judge_hint: "Watch the first Spark corridor get rejected if it crosses flood water, then re-routed and verified before Wonder dispatches.",
  },
  {
    id: "earthquake-bridge", name: "Earthquake Bridge & Rubble Triage", disaster_type: "earthquake",
    description: "Earthquake-damaged district: cracked, partly collapsed bridge, rubble-blocked streets, damaged buildings. Prioritise debris clearance, medical access and a flat landing zone.",
    image_path: "/presets/earthquake-bridge.jpg", image_filename: "earthquake-bridge.jpg",
    image_provenance: "Demo scene generated with muse-image-1.0. Hazard claims come from live sam-3.1 at click time.",
    audio_path: null, audio_filename: null,
    field_report: "Strong earthquake has cracked the river bridge and dropped rubble across the main street. People are trapped in damaged buildings on both sides of the river. Need heavy debris clearance, medical teams, and a clear flat landing zone on undamaged ground.",
    latitude: 38.4237, longitude: 27.1428,
    expected_focus: ["debris", "damaged building", "bridge", "clear flat ground", "road"],
    judge_hint: "Check whether the bridge segments as passable or damaged, and whether the verifier keeps corridors off the rubble.",
  },
  {
    id: "wildfire-helipad", name: "Wildfire Evacuation & Helipad Finder", disaster_type: "wildfire",
    description: "Wildfire front approaching a rural town: fire and scorched ground on the ridge, one winding evacuation road, open field for a helipad. Verify an evacuation corridor away from the fire line.",
    image_path: "/presets/wildfire-helipad.jpg", image_filename: "wildfire-helipad.jpg",
    image_provenance: "Demo scene generated with muse-image-1.0. Hazard claims come from live sam-3.1 at click time.",
    audio_path: null, audio_filename: null,
    field_report: "Wildfire front is moving toward town from the forested ridge and smoke is crossing the west road. Residents need an evacuation route away from the fire line, and helicopters need a clear flat helipad on open ground well clear of the flames.",
    latitude: 39.2, longitude: -120.9,
    expected_focus: ["fire", "road", "clear flat ground", "rooftop", "debris"],
    judge_hint: "The landing zone must clear the fire detections with real clearance area - watch the clearance numbers in the trace.",
  },
];
