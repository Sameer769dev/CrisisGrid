// Global disaster scenario metadata - mirrors GET /api/presets (backend/services/presets.py).
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
    image_provenance: "Pre-loaded aerial flood demo frame (live-flood.jpg). Segmentation and geometric verification run live on click - nothing is pre-baked.",
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
    image_provenance: "Synthetic tactical scenario generated with muse-image-1.0. Hazard claims come from live sam-3.1 at click time.",
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
    image_provenance: "Synthetic tactical scenario generated with muse-image-1.0. Hazard claims come from live sam-3.1 at click time.",
    audio_path: null, audio_filename: null,
    field_report: "Wildfire front is moving toward town from the forested ridge and smoke is crossing the west road. Residents need an evacuation route away from the fire line, and helicopters need a clear flat helipad on open ground well clear of the flames.",
    latitude: 39.2, longitude: -120.9,
    expected_focus: ["fire", "road", "clear flat ground", "rooftop", "debris"],
    judge_hint: "The landing zone must clear the fire detections with real clearance area - watch the clearance numbers in the trace.",
  },
];

export interface DisasterTestImage {
  id: string;
  name: string;
  category: "flood" | "earthquake" | "landslide" | "cyclone" | "tornado" | "wildfire" | "post-clearance";
  region: string;
  image_path: string;
  image_filename: string;
  audio_path: string | null;
  audio_filename: string | null;
  latitude: number;
  longitude: number;
  field_report: string;
  after_pair_path?: string;
  after_pair_filename?: string;
}

export const DISASTER_TEST_IMAGES: DisasterTestImage[] = [
  {
    id: "urban-flood",
    name: "Urban Flood Corridor",
    category: "flood",
    region: "Kathmandu Valley, Nepal",
    image_path: "/presets/urban-flood.jpg",
    image_filename: "urban-flood.jpg",
    audio_path: "/presets/field-radio.wav",
    audio_filename: "field-radio.wav",
    latitude: 27.7172,
    longitude: 85.3240,
    field_report: "Flood water across the low road and market area, residents stranded on rooftops, water still rising. Need boat rescue teams and a high-ground helicopter landing zone. The bridge on the east side may still be passable - please verify before sending vehicles.",
    after_pair_path: "/presets/flash-flood-bridge.jpg",
    after_pair_filename: "flash-flood-bridge.jpg",
  },
  {
    id: "flash-flood-bridge",
    name: "River Flash Flood & Overpass",
    category: "flood",
    region: "Sylhet Basin, Bangladesh",
    image_path: "/presets/flash-flood-bridge.jpg",
    image_filename: "flash-flood-bridge.jpg",
    audio_path: "/presets/field-radio.wav",
    audio_filename: "field-radio.wav",
    latitude: 24.8949,
    longitude: 91.8687,
    field_report: "Flash flood has submerged the lower riverbank road and stranded a vehicle near the embankment. The elevated concrete bridge and upper highway appear dry - verify a safe evacuation corridor across the bridge and a helicopter landing zone on the high athletic field.",
  },
  {
    id: "coastal-tsunami",
    name: "Coastal Storm Surge & Causeway",
    category: "cyclone",
    region: "Odisha Coast, India",
    image_path: "/presets/coastal-tsunami.jpg",
    image_filename: "coastal-tsunami.jpg",
    audio_path: null,
    audio_filename: null,
    latitude: 19.8135,
    longitude: 85.8312,
    field_report: "Cyclone storm surge has inundated low coastal streets with two stranded vehicles and residents waiting on a flat concrete rooftop. Verify whether the elevated concrete causeway bridge leading inland is clear of flood water and locate a flat asphalt staging lot for medevac.",
  },
  {
    id: "earthquake-bridge",
    name: "Earthquake Bridge & Rubble",
    category: "earthquake",
    region: "Izmir Province, Turkey",
    image_path: "/presets/earthquake-bridge.jpg",
    image_filename: "earthquake-bridge.jpg",
    audio_path: null,
    audio_filename: null,
    latitude: 38.4237,
    longitude: 27.1428,
    field_report: "Strong earthquake has cracked the river bridge and dropped rubble across the main street. People are trapped in damaged buildings on both sides of the river. Need heavy debris clearance, medical teams, and a clear flat landing zone on undamaged ground.",
    after_pair_path: "/presets/earthquake-bridge-cleared.jpg",
    after_pair_filename: "earthquake-bridge-cleared.jpg",
  },
  {
    id: "landslide-highway",
    name: "Mountain Landslide & Gorge Bridge",
    category: "landslide",
    region: "Pokhara Highway, Nepal",
    image_path: "/presets/landslide-highway.jpg",
    image_filename: "landslide-highway.jpg",
    audio_path: null,
    audio_filename: null,
    latitude: 28.2096,
    longitude: 83.9856,
    field_report: "Heavy monsoon landslide has dumped mud and boulders across the left bend of the mountain highway. Check whether the concrete gorge bridge and right-side road lane avoid the debris footprint, and verify the flat gravel turnout for a rotary-wing supply drop.",
  },
  {
    id: "tornado-corridor",
    name: "Tornado Debris & Arterial Road",
    category: "tornado",
    region: "Moore, Oklahoma, USA",
    image_path: "/presets/tornado-corridor.jpg",
    image_filename: "tornado-corridor.jpg",
    audio_path: null,
    audio_filename: null,
    latitude: 35.3395,
    longitude: -97.4867,
    field_report: "EF4 tornado tore roofs off residential blocks along the west street and scattered timber debris. The four-lane north-south arterial road and overpass bridge appear intact - verify a debris-free ambulance corridor and confirm clearance on the southeast park field for air ambulance landing.",
  },
  {
    id: "wildfire-helipad",
    name: "Wildfire Front & Helipad Meadow",
    category: "wildfire",
    region: "Sierra Nevada, California, USA",
    image_path: "/presets/wildfire-helipad.jpg",
    image_filename: "wildfire-helipad.jpg",
    audio_path: null,
    audio_filename: null,
    latitude: 39.2000,
    longitude: -120.9000,
    field_report: "Wildfire front is moving toward town from the forested ridge and smoke is crossing the west road. Residents need an evacuation route away from the fire line, and helicopters need a clear flat helipad on open ground well clear of the flames.",
    after_pair_path: "/presets/wildfire-ridge-road.jpg",
    after_pair_filename: "wildfire-ridge-road.jpg",
  },
  {
    id: "wildfire-ridge-road",
    name: "Valley Brush Fire & Creek Bridge",
    category: "wildfire",
    region: "Valparaíso Hills, Chile",
    image_path: "/presets/wildfire-ridge-road.jpg",
    image_filename: "wildfire-ridge-road.jpg",
    audio_path: null,
    audio_filename: null,
    latitude: -33.0472,
    longitude: -71.6127,
    field_report: "Brush fire burning along the dry hillside ridge to the west. Verify that the paved two-lane valley road and concrete creek bridge stay completely clear of the fire zone, and certify the foreground green pasture meadow as a helicopter landing zone.",
  },
  {
    id: "earthquake-bridge-cleared",
    name: "Post-Clearance Corridor (After Frame)",
    category: "post-clearance",
    region: "Izmir Province, Turkey (Cleared)",
    image_path: "/presets/earthquake-bridge-cleared.jpg",
    image_filename: "earthquake-bridge-cleared.jpg",
    audio_path: null,
    audio_filename: null,
    latitude: 38.4237,
    longitude: 27.1428,
    field_report: "Heavy engineering teams have cleared the rubble from the main asphalt road and river bridge. Re-verify the primary evacuation corridor and foreground plaza landing zone to unlock medical and logistics dispatch.",
  },
];
