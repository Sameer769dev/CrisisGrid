// Typed client for the CrisisGrid FastAPI backend. No secrets here - MODEL_API_KEY stays backend-only.
const PROD_MODAL_URL = "https://baralsamir941--crisisgrid-api-crisisgrid-asgi.us-east.modal.run";

export function normalizeBackendUrl(raw?: string): string {
  let cleaned = (raw ?? "").trim().replace(/\/+$/, "");
  cleaned = cleaned.replace(/\/health$/i, "");
  if (cleaned && !/^(https?:\/\/)?(localhost|127\.0\.0\.1)(:\d+)?$/i.test(cleaned) && !/\.modal\.run$/i.test(cleaned)) return PROD_MODAL_URL;
  if (!cleaned) {
    if (typeof window !== "undefined") {
      const host = window.location.hostname;
      if (host !== "localhost" && host !== "127.0.0.1") {
        return PROD_MODAL_URL;
      }
    }
    return "http://localhost:8000";
  }
  if (!/^https?:\/\//i.test(cleaned)) {
    const isLocal = /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(cleaned);
    cleaned = `${isLocal ? "http" : "https"}://${cleaned}`;
  }
  return cleaned;
}

export const API_BASE_URL = normalizeBackendUrl(
  process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL,
);

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const isRemoteBrowser =
    typeof window !== "undefined" &&
    window.location.hostname !== "localhost" &&
    window.location.hostname !== "127.0.0.1";
  const primaryUrl = isRemoteBrowser ? `/cg-api${path}` : `${API_BASE_URL}${path}`;
  const fallbackUrl = isRemoteBrowser ? `${API_BASE_URL}${path}` : `/cg-api${path}`;
  try {
    const res = await fetch(primaryUrl, init);
    if (isRemoteBrowser && (res.status === 404 || res.status === 504)) {
      return await fetch(fallbackUrl, init);
    }
    return res;
  } catch {
    return await fetch(fallbackUrl, init);
  }
}

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  compute_runtime?: string;
  meta_api_base_url: string;
  model_api_key_configured: boolean;
  models: Record<string, string>;
}

export interface SamDetection {
  x1: number; y1: number; x2: number; y2: number; w: number; h: number;
  mask_x: number | null; mask_y: number | null; mask_data: string | null;
}


export type ScanConceptKind = "hazard" | "safe_zone" | "custom";

export interface NormalizedBox {
  x_min: number; y_min: number; x_max: number; y_max: number;
  width: number; height: number;
}

export interface ScanMask {
  x: number | null; y: number | null; width: number; height: number;
  format: "sam-3.1-rle"; data: string;
}

export interface ScanDetection {
  concept: string;
  kind: ScanConceptKind;
  color: string;
  bbox_px: { x1: number; y1: number; x2: number; y2: number };
  bbox: NormalizedBox;
  bbox_xyxy_norm: [number, number, number, number];
  area_fraction: number;
  mask: ScanMask | null;
  has_mask: boolean;
}

export interface ConceptLayer {
  concept: string;
  kind: ScanConceptKind;
  color: string;
  model: "sam-3.1";
  status: "ok" | "error";
  latency_ms: number;
  detection_count: number;
  mask_count: number;
  sam_image_size: { width: number; height: number } | null;
  detections: ScanDetection[];
  error: { type: string; message: string } | null;
}

export interface ScanTraceEntry {
  step: string;
  event: string;
  detail: string;
  state: string;
  concept?: string;
  kind?: ScanConceptKind;
  status?: string;
  latency_ms?: number;
  detections?: number;
  masks?: number;
}

export interface ScanHazardsResult {
  status: "ok" | "partial" | "failed";
  model: "sam-3.1";
  image: {
    filename: string | null;
    media_type: string;
    width: number | null;
    height: number | null;
    size_bytes: number;
  };
  concepts_requested: string[];
  concept_layers: ConceptLayer[];
  detections: ScanDetection[];
  summary: {
    total_detections: number;
    total_masks: number;
    concepts_succeeded: number;
    concepts_failed: number;
    total_latency_ms: number;
    hazards: { concepts_with_detections: string[]; detections: number; masks: number; box_area_fraction_sum: number };
    safe_zones: { concepts_with_detections: string[]; detections: number; masks: number; box_area_fraction_sum: number };
  };
  trace: ScanTraceEntry[];
  verification_status: "unverified_segmentation_only";
}

export interface ScanConcepts {
  model: "sam-3.1";
  hazards: { concept: string; kind: "hazard"; color: string }[];
  safe_zones: { concept: string; kind: "safe_zone"; color: string }[];
  note: string;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthStatus> {
  const res = await apiFetch(`/health`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`Backend /health failed: ${res.status}`);
  return res.json();
}


export async function fetchScanConcepts(signal?: AbortSignal): Promise<ScanConcepts> {
  const res = await apiFetch(`/api/scan-hazards/concepts`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`Backend /api/scan-hazards/concepts failed: ${res.status}`);
  return res.json();
}

/** Day 2: parallel sam-3.1 segmentation. The backend fans out to one Meta request per concept. */
export async function scanHazards(
  image: File | Blob,
  concepts?: string[],
  signal?: AbortSignal,
): Promise<ScanHazardsResult> {
  const form = new FormData();
  form.append("file", image);
  if (concepts?.length) form.append("concepts", concepts.join(","));
  const res = await apiFetch(`/api/scan-hazards`, {
    method: "POST",
    body: form,
    signal,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = "";
    try { detail = JSON.stringify(await res.json()); } catch { /* keep status-only error */ }
    throw new Error(`Backend /api/scan-hazards failed: ${res.status}${detail ? " " + detail : ""}`);
  }
  return res.json();
}


export interface NormPoint { x: number; y: number }

export interface TriagePriority {
  rank: number;
  category: string;
  action: string;
  rationale: string;
  target_concepts: string[];
  location_hint: string | null;
}

export interface CandidateCorridor {
  id: string;
  name: string;
  purpose: string;
  points_norm: NormPoint[];
  start_label: string;
  end_label: string;
  rationale: string;
  grounded_concepts: string[];
  status: "unverified_candidate";
  color: string;
  coordinate_space: "normalized_image_0_1";
  requires_day4_verification: true;
}

export interface CandidateLandingZone {
  id: string;
  name: string;
  center_norm: NormPoint;
  radius_norm: number;
  surface_concept: string;
  rationale: string;
  grounded_concepts: string[];
  status: "unverified_candidate";
  color: string;
  coordinate_space: "normalized_image_0_1";
  requires_day4_verification: true;
}

export interface TriageResult {
  status: string;
  day: 3;
  models: { transcription: string; triage: string };
  input: {
    source: "audio_transcription" | "text_fallback";
    has_audio: boolean;
    has_image: boolean;
    image_filename: string | null;
    has_scan: boolean;
    scan_id: string | null;
  };
  transcription: {
    status: string;
    model: string | null;
    source: string;
    transcript: string;
    latency_ms: number;
    audio: Record<string, unknown> | null;
  };
  transcript: string;
  triage: {
    incident_type: string;
    severity: "critical" | "high" | "moderate" | "low" | "unknown";
    urgency_score: number;
    summary: string;
    people_at_risk: { count_estimate: number | null; description: string; confidence: number };
    hazards_identified: string[];
    passable_infrastructure: string[];
    blocked_infrastructure: string[];
    priorities: TriagePriority[];
    candidate_evacuation_corridors: CandidateCorridor[];
    candidate_landing_zones: CandidateLandingZone[];
    recommended_units: { unit_type: string; task: string; priority_rank: number | null }[];
    missing_information: string[];
    assumptions: string[];
    confidence: number;
  };
  candidate_evacuation_corridors: CandidateCorridor[];
  candidate_landing_zones: CandidateLandingZone[];
  grounding: { scan: Record<string, unknown>; grounded_concepts: string[] };
  trace: ScanTraceEntry[];
  total_latency_ms: number;
  verification_status: "unverified_triage_proposal";
  next_step: string;
}

export interface TriageTextRequest {
  text: string;
  scan_result?: ScanHazardsResult | Record<string, unknown> | null;
  scan_id?: string | null;
}

/** Day 3 JSON text fallback: typed field report + optional Day 2 scan payload. */
export async function triageText(payload: TriageTextRequest, signal?: AbortSignal): Promise<TriageResult> {
  const res = await apiFetch(`/api/triage/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = "";
    try { detail = JSON.stringify(await res.json()); } catch { /* keep status-only error */ }
    throw new Error(`Backend /api/triage/text failed: ${res.status}${detail ? " " + detail : ""}`);
  }
  return res.json();
}

/** Day 3 multipart: field-radio WAV and/or text, optional Day 2 scan JSON + image. */
export async function triageReport(
  input: {
    audio?: File | Blob | null;
    text?: string | null;
    scanResult?: ScanHazardsResult | Record<string, unknown> | null;
    scanId?: string | null;
    image?: File | Blob | null;
  },
  signal?: AbortSignal,
): Promise<TriageResult> {
  const form = new FormData();
  if (input.audio) form.append("audio", input.audio);
  if (input.text) form.append("text", input.text);
  if (input.scanResult) form.append("scan_json", JSON.stringify(input.scanResult));
  if (input.scanId) form.append("scan_id", input.scanId);
  if (input.image) form.append("image", input.image);
  const res = await apiFetch(`/api/triage`, {
    method: "POST",
    body: form,
    signal,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = "";
    try { detail = JSON.stringify(await res.json()); } catch { /* keep status-only error */ }
    throw new Error(`Backend /api/triage failed: ${res.status}${detail ? " " + detail : ""}`);
  }
  return res.json();
}


export interface VerifyRequest {
  scan_result: ScanHazardsResult | Record<string, unknown>;
  triage_result?: TriageResult | Record<string, unknown> | null;
  candidate_evacuation_corridors?: Record<string, unknown>[] | null;
  candidate_landing_zones?: Record<string, unknown>[] | null;
  latitude?: number | null;
  longitude?: number | null;
  facility_radius_m?: number;
  auto_correct?: boolean;
  max_correction_attempts?: number;
  max_hazard_intersection_ratio?: number;
}

export interface CandidateVerification {
  candidate_id: string;
  kind: "evacuation_corridor" | "landing_zone";
  status: "verified" | "rejected";
  color: string;
  method: "mask" | "bbox";
  hazard_intersection_ratio: number;
  hazard_threshold: number;
  safe_support_ratio?: number;
  safe_surface_overlap_ratio?: number;
  hazard_footprint_iou?: number;
  hazard_iou?: number;
  clearance?: Record<string, unknown>;
  intersecting_hazards: Record<string, unknown>[];
  reasons: string[];
  requires_reroute: boolean;
}

export interface VerifyResult {
  status: "verified" | "rejected" | "partially_verified" | "no_candidates";
  day: 4;
  engine: "deterministic_python";
  model_calls_in_geometry: 0;
  correction_model: string | null;
  verified_candidates: { corridors: Record<string, unknown>[]; landing_zones: Record<string, unknown>[] };
  rejected_candidates: { corridors: CandidateVerification[]; landing_zones: CandidateVerification[] };
  correction: {
    enabled: boolean; max_attempts: number; attempts_used: number;
    status: string; history: Record<string, unknown>[];
  };
  emergency_facilities: {
    status: string; facilities: { name: string; type: string; distance_m: number }[];
    counts_by_type: Record<string, number>;
  };
  final_verification: {
    corridor_results: CandidateVerification[];
    landing_zone_results: CandidateVerification[];
    summary: { total: number; verified: number; rejected: number };
    field: Record<string, unknown>;
    method: "mask" | "bbox";
  };
  trace: ScanTraceEntry[];
  total_latency_ms: number;
  verification_status: string;
  dispatch_ready: boolean;
  next_step: string;
}

/** Day 4: deterministic verification; Spark re-routes only when the verifier rejects. */
export async function verifyCandidates(payload: VerifyRequest, signal?: AbortSignal): Promise<VerifyResult> {
  const res = await apiFetch(`/api/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = "";
    try { detail = JSON.stringify(await res.json()); } catch { /* keep status-only error */ }
    throw new Error(`Backend /api/verify failed: ${res.status}${detail ? " " + detail : ""}`);
  }
  return res.json();
}

// Day 2: POST /api/scan-hazards (alias /api/scan)  |  Day 3: POST /api/triage + /api/triage/text
// Day 4: POST /api/verify  |  Day 5: POST /api/dispatch + POST /api/run-crisisgrid (all live)
// The UI must surface rejections, held units, and skipped dispatch honestly - never fake output.

export interface DispatchUnitAssignment {
  unit_id: string;
  unit_type: string;
  task: string;
  target_candidate_id: string | null;
  requested_target_candidate_id?: string;
  target_kind: string;
  staging: string;
  priority_rank: number | null;
  eta_minutes_estimate: number | null;
  rationale: string;
  dispatch_status: "dispatched" | "held";
  color: string;
  guardrail_flags: string[];
}

export interface BriefingCard {
  status: "ok" | "failed";
  model: "muse-image-1.0";
  format: "png";
  image_base64: string | null;
  image_url: string | null;
  image_size_bytes?: number | null;
  prompt: string;
  latency_ms: number;
  error: { type: string; message: string } | null;
}

export interface DispatchPlan {
  operation_name: string;
  command_summary: string;
  situation_assessment: string;
  units: DispatchUnitAssignment[];
  phases: { phase: number; name: string; actions: string[] }[];
  safety_brief: string[];
  communications_plan: string;
  logistics_notes: string[];
  assumptions: string[];
  confidence: number;
  summary_counts: { units_total: number; units_dispatched: number; units_held: number };
}

export interface DispatchResult {
  status: "ok";
  day: 5;
  models: { dispatch: "muse-wonder-1.0"; briefing_image: "muse-image-1.0" };
  reasoning: { effort: "high" };
  input_basis: {
    verified_corridors: string[];
    verified_landing_zones: string[];
    excluded_rejected_candidate_ids: string[];
    gate_excluded: { candidate_id: string; kind: string; reason: string }[];
    dispatch_basis: string;
  };
  dispatch: DispatchPlan;
  guardrail: {
    engine: "deterministic_python";
    model_calls: 0;
    actions: { unit_id: string; action: string; detail: string }[];
    units_dispatched: number;
    units_held: number;
  };
  briefing_card: BriefingCard | null;
  trace: ScanTraceEntry[];
  total_latency_ms: number;
  verification_status: "dispatch_from_verified_candidates_only";
  next_step: string;
}

export interface DispatchRequestBody {
  verification_result?: VerifyResult | Record<string, unknown> | null;
  verified_candidates?: { corridors: Record<string, unknown>[]; landing_zones: Record<string, unknown>[] } | null;
  triage_result?: TriageResult | Record<string, unknown> | null;
  include_briefing_card?: boolean;
}

export interface DispatchReadiness {
  models: { dispatch: string; briefing_image: string };
  reasoning: { effort: string };
  input: string;
  guardrail: string;
  briefing_card: string;
  output: string;
}

export async function fetchDispatchReadiness(signal?: AbortSignal): Promise<DispatchReadiness> {
  const res = await apiFetch(`/api/dispatch/readiness`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`Backend /api/dispatch/readiness failed: ${res.status}`);
  return res.json();
}

/**
 * Day 5: verified state -> muse-wonder-1.0 multi-unit dispatch + muse-image-1.0 card.
 * The backend re-gates every candidate deterministically; units aimed at
 * unverified targets come back "held" (yellow), never dispatched (green).
 */
export async function runDispatch(payload: DispatchRequestBody, signal?: AbortSignal): Promise<DispatchResult> {
  const res = await apiFetch(`/api/dispatch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = "";
    try { detail = JSON.stringify(await res.json()); } catch { /* keep status-only error */ }
    throw new Error(`Backend /api/dispatch failed: ${res.status}${detail ? " " + detail : ""}`);
  }
  return res.json();
}

export interface CrisisGridRunResult {
  status: "ok" | "completed_no_dispatch";
  day: 5;
  pipeline: string[];
  stages: {
    scan: { status: string; detections: number | null; latency_ms: number | null };
    triage: {
      severity: string | null; urgency_score: number | null;
      candidate_corridors: number; candidate_landing_zones: number;
    };
    verification: {
      status: string; verified: number | null; rejected: number | null; dispatch_ready: boolean;
    };
    dispatch: Record<string, unknown>;
  };
  scan: ScanHazardsResult;
  triage: TriageResult;
  verification: VerifyResult;
  dispatch: DispatchResult | null;
  dispatch_block: { status: string; message: string } | null;
  briefing_card: BriefingCard | null;
  trace: ScanTraceEntry[];
  total_latency_ms: number;
  verification_status: string;
  next_step: string;
}

/**
 * Day 5 unified pipeline in one multipart call:
 * sam-3.1 scan -> radio/text + muse-spark-1.3 triage -> deterministic
 * verification -> muse-wonder-1.0 dispatch + muse-image-1.0 briefing card.
 * If nothing verifies, dispatch stays null - the UI must show that honestly.
 */
export async function runCrisisGrid(
  input: {
    image: File | Blob;
    audio?: File | Blob | null;
    text?: string | null;
    latitude?: number | null;
    longitude?: number | null;
    facilityRadiusM?: number;
    autoCorrect?: boolean;
    maxCorrectionAttempts?: number;
    includeBriefingCard?: boolean;
    concepts?: string[] | null;
  },
  signal?: AbortSignal,
): Promise<CrisisGridRunResult> {
  const form = new FormData();
  form.append("image", input.image);
  if (input.audio) form.append("audio", input.audio);
  if (input.text) form.append("text", input.text);
  if (input.latitude != null) form.append("latitude", String(input.latitude));
  if (input.longitude != null) form.append("longitude", String(input.longitude));
  if (input.facilityRadiusM != null) form.append("facility_radius_m", String(input.facilityRadiusM));
  if (input.autoCorrect != null) form.append("auto_correct", String(input.autoCorrect));
  if (input.maxCorrectionAttempts != null) form.append("max_correction_attempts", String(input.maxCorrectionAttempts));
  if (input.includeBriefingCard != null) form.append("include_briefing_card", String(input.includeBriefingCard));
  if (input.concepts?.length) form.append("concepts", input.concepts.join(","));
  const res = await apiFetch(`/api/run-crisisgrid`, {
    method: "POST",
    body: form,
    signal,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = "";
    try { detail = JSON.stringify(await res.json()); } catch { /* keep status-only error */ }
    throw new Error(`Backend /api/run-crisisgrid failed: ${res.status}${detail ? " " + detail : ""}`);
  }
  return res.json();
}

// --------------------------------------------------------------------------- //
// Day 7: before/after damage delta, post-clearance re-verification, sectors
// --------------------------------------------------------------------------- //
export interface DeltaDetection {
  concept: string; kind: "hazard" | "safe_zone"; semantic_kind: string;
  delta_status: "new" | "cleared" | "persistent"; color: string;
  bbox: NormalizedBox; bbox_xyxy_norm: [number, number, number, number];
  area_fraction: number; matched_iou: number | null;
  counterpart_area_fraction: number | null; has_mask: boolean; mask: ScanMask | null;
}

export interface DeltaResult {
  status: "ok"; day: 7; engine: "deterministic_python"; model_calls: 0;
  match_iou_threshold: number;
  frames: { before: { detections: number; width: number | null; height: number | null }; after: { detections: number; width: number | null; height: number | null } };
  warnings: string[]; verdict: string;
  summary: Record<string, number>;
  per_concept: { concept: string; kind: string; before_count: number; after_count: number; persistent: number; new: number; cleared: number; box_area_fraction_before: number; box_area_fraction_after: number; box_area_fraction_delta: number }[];
  delta_detections: DeltaDetection[];
  trace: ScanTraceEntry[]; total_latency_ms: number;
  verification_status: string; next_step: string;
}

export async function computeDelta(scanBefore: ScanHazardsResult, scanAfter: ScanHazardsResult, iouThreshold = 0.1, signal?: AbortSignal): Promise<DeltaResult> {
  const res = await apiFetch(`/api/delta`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scan_before: scanBefore, scan_after: scanAfter, iou_threshold: iouThreshold }),
    signal, cache: "no-store",
  });
  if (!res.ok) { let d = ""; try { d = JSON.stringify(await res.json()); } catch { /* status only */ } throw new Error(`Backend /api/delta failed: ${res.status}${d ? " " + d : ""}`); }
  return res.json();
}

export interface ClearanceResult {
  status: "ok"; day: 7; engine: "deterministic_python"; model_calls: 0;
  verdict: string;
  status_changes: { candidate_id: string; kind: string; before_status: string; after_status: string; before_hazard_intersection_ratio: number | null; after_hazard_intersection_ratio: number | null; flipped_to_verified: boolean; flipped_to_rejected: boolean; reasons: string[] }[];
  flipped_to_verified: string[]; still_blocked: string[];
  verification_result: VerifyResult;
  trace: ScanTraceEntry[]; total_latency_ms: number;
  verification_status: string; dispatch_ready: boolean; next_step: string;
}

export async function verifyClearance(payload: {
  scanAfter: ScanHazardsResult; triageResult?: TriageResult | null;
  candidateCorridors?: Record<string, unknown>[] | null; candidateLandingZones?: Record<string, unknown>[] | null;
  verificationBefore?: VerifyResult | null;
}, signal?: AbortSignal): Promise<ClearanceResult> {
  const res = await apiFetch(`/api/delta/verify-clearance`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scan_after: payload.scanAfter, triage_result: payload.triageResult ?? null,
      candidate_evacuation_corridors: payload.candidateCorridors ?? null,
      candidate_landing_zones: payload.candidateLandingZones ?? null,
      verification_before: payload.verificationBefore ?? null,
    }),
    signal, cache: "no-store",
  });
  if (!res.ok) { let d = ""; try { d = JSON.stringify(await res.json()); } catch { /* status only */ } throw new Error(`Backend /api/delta/verify-clearance failed: ${res.status}${d ? " " + d : ""}`); }
  return res.json();
}

export interface RankedSector {
  rank: number; sector_id: string; name: string; score: number;
  severity: string; urgency_score: number; people_at_risk: number | null;
  hazard_area_fraction_sum: number; candidates_total: number;
  candidates_verified: number; candidates_rejected: number;
  dispatch_ready: boolean; recommended_action: string;
  breakdown: { urgency_component: number; severity_component: number; people_component: number; hazard_component: number; access_component: number; access_note: string };
}

export interface SectorRankResult {
  status: "ok"; day: 7; engine: "deterministic_python"; model_calls: 0;
  formula: string; ranked_sectors: RankedSector[];
  trace: ScanTraceEntry[]; total_latency_ms: number;
  verification_status: string; next_step: string;
}

export async function rankSectors(sectors: Record<string, unknown>[], signal?: AbortSignal): Promise<SectorRankResult> {
  const res = await apiFetch(`/api/sectors/rank`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sectors }), signal, cache: "no-store",
  });
  if (!res.ok) { let d = ""; try { d = JSON.stringify(await res.json()); } catch { /* status only */ } throw new Error(`Backend /api/sectors/rank failed: ${res.status}${d ? " " + d : ""}`); }
  return res.json();
}

// Global scenario preset catalogue + Live USGS seismic telemetry client.
export interface PresetsResult { status: string; day: 8; count: number; presets: import("./presets").CrisisPreset[]; honesty_note: string; next_step: string }
export async function fetchPresets(signal?: AbortSignal): Promise<PresetsResult> {
  const res = await apiFetch(`/api/presets`, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`Backend /api/presets failed: ${res.status}`);
  return res.json();
}

export interface UsgsEvent {
  event_id: string;
  title: string;
  place: string;
  magnitude: number | null;
  depth_km: number | null;
  latitude: number;
  longitude: number;
  time_epoch_ms: number | null;
  time_iso: string | null;
  alert_level: string | null;
  tsunami_warning: boolean;
  felt_reports: number | null;
  mmi_intensity: number | null;
  usgs_url: string | null;
  severity_estimate: string;
  urgency_estimate: number;
  recommended_preset_id: string;
  field_report: string;
}

export interface UsgsLiveResult {
  status: "ok";
  provider: string;
  feed: string;
  feed_url: string;
  feed_title: string;
  model_calls: 0;
  min_magnitude: number;
  total_matching: number;
  count: number;
  events: UsgsEvent[];
  latency_ms: number;
  trace: ScanTraceEntry[];
  next_step: string;
}

export async function fetchUsgsLive(feed = "4.5_day", minMagnitude = 4.5, limit = 6, signal?: AbortSignal): Promise<UsgsLiveResult> {
  const qs = new URLSearchParams({ feed, min_magnitude: String(minMagnitude), limit: String(limit) });
  const res = await apiFetch(`/api/usgs/live?${qs.toString()}`, { signal, cache: "no-store" });
  if (!res.ok) {
    let d = "";
    try { d = JSON.stringify(await res.json()); } catch { /* status only */ }
    throw new Error(`Backend /api/usgs/live failed: ${res.status}${d ? " " + d : ""}`);
  }
  return res.json();
}
