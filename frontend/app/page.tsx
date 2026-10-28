"use client";
// CrisisGrid Tactical Command - Autonomous Multimodal Disaster Triage & Dispatch UI.
// End-to-end operator flow in one browser session: upload -> SCAN (sam-3.1) -> TRIAGE
// (muse-voice-transcribe-1.0 + muse-spark-1.3) -> VERIFY (deterministic Python,
// the only component allowed to mark anything green) -> DISPATCH
// (muse-wonder-1.0 + muse-image-1.0), or one-click RUN FULL PIPELINE.
import { useEffect, useMemo, useState } from "react";
import TacticalCanvas, { type CanvasCorridor, type CanvasZone, type InspectItem } from "@/components/TacticalCanvas";
import AgentTrace from "@/components/AgentTrace";
import DispatchConsole from "@/components/DispatchConsole";
import {
  computeDelta, fetchHealth, fetchPresets, fetchUsgsLive, rankSectors, runCrisisGrid, runDispatch, scanHazards, triageReport,
  verifyCandidates, verifyClearance,
  type ClearanceResult, type DeltaResult, type DispatchResult, type HealthStatus,
  type ScanDetection, type ScanHazardsResult, type ScanTraceEntry, type SectorRankResult,
  type TriageResult, type UsgsEvent, type UsgsLiveResult, type VerifyResult,
} from "@/lib/api";
import { DeltaPanel, SectorPanel, type SectorSnapshot } from "@/components/Day7Panels";
import PresetPanel from "@/components/PresetPanel";
import { DISASTER_TEST_IMAGES, FALLBACK_PRESETS, type CrisisPreset, type DisasterTestImage } from "@/lib/presets";

type Stage = "scan" | "triage" | "verify" | "dispatch" | "pipeline";
type StageState = "idle" | "running" | "done" | "error" | "blocked";

const HAZARDS = ["flood water", "debris", "fire", "damaged building", "stranded vehicle"];
const SAFE = ["road", "bridge", "clear flat ground", "rooftop"];
const ALL_CONCEPTS = [...HAZARDS, ...SAFE];

export default function Home() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [backendDown, setBackendDown] = useState(false);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [fieldText, setFieldText] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [scan, setScan] = useState<ScanHazardsResult | null>(null);
  const [triage, setTriage] = useState<TriageResult | null>(null);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [dispatch, setDispatch] = useState<DispatchResult | null>(null);
  const [dispatchBlock, setDispatchBlock] = useState<{ status: string; message: string } | null>(null);
  const [includeCard, setIncludeCard] = useState(true);
  // Damage delta, clearance re-verification, and multi-sector triage state.
  const [afterFile, setAfterFile] = useState<File | null>(null);
  const [afterUrl, setAfterUrl] = useState<string | null>(null);
  const [afterScan, setAfterScan] = useState<ScanHazardsResult | null>(null);
  const [delta, setDelta] = useState<DeltaResult | null>(null);
  const [clearance, setClearance] = useState<ClearanceResult | null>(null);
  const [viewMode, setViewMode] = useState<"live" | "delta">("live");
  const [day7Busy, setDay7Busy] = useState(false);
  const [sectorName, setSectorName] = useState("");
  const [sectorStore, setSectorStore] = useState<{ id: string; name: string; savedAt: string; imageUrl: string | null; scan: ScanHazardsResult | null; triage: TriageResult | null; verify: VerifyResult | null }[]>([]);
  const [sectorRank, setSectorRank] = useState<SectorRankResult | null>(null);
  // Global disaster preset catalogue (API with local fallback).
  const [presets, setPresets] = useState<CrisisPreset[]>(FALLBACK_PRESETS);
  const [presetSource, setPresetSource] = useState<"api" | "fallback">("fallback");
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [usgs, setUsgs] = useState<UsgsLiveResult | null>(null);
  const [usgsBusy, setUsgsBusy] = useState(false);
  const [sampleFilter, setSampleFilter] = useState<string>("all");
  const filteredSamples = useMemo(() => sampleFilter === "all" ? DISASTER_TEST_IMAGES : DISASTER_TEST_IMAGES.filter((s) => s.category === sampleFilter), [sampleFilter]);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchPresets(ctrl.signal).then((r) => { setPresets(r.presets); setPresetSource("api"); }).catch(() => { /* fallback stays */ });
    return () => ctrl.abort();
  }, []);
  const [stage, setStage] = useState<Record<Stage, StageState>>({ scan: "idle", triage: "idle", verify: "idle", dispatch: "idle", pipeline: "idle" });
  const [error, setError] = useState<string | null>(null);
  const [visibleConcepts, setVisibleConcepts] = useState<Set<string>>(new Set(ALL_CONCEPTS));
  const [showCorridors, setShowCorridors] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [selected, setSelected] = useState<InspectItem>(null);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchHealth(ctrl.signal).then((h) => { setHealth(h); setBackendDown(false); }).catch(() => setBackendDown(true));
    return () => ctrl.abort();
  }, []);

  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);

  const keyReady = health?.model_api_key_configured;
  const busy = Object.values(stage).some((s) => s === "running");

  const trace: ScanTraceEntry[] = useMemo(() => {
    const out: ScanTraceEntry[] = [];
    if (scan) out.push(...scan.trace);
    if (triage) out.push(...triage.trace);
    // When clearance applied, verify IS the clearance wrapper and its trace
    // equals clearance.trace - push it once, via clearance, to avoid dupes.
    if (verify && !clearance) out.push(...verify.trace);
    if (dispatch) out.push(...dispatch.trace);
    if (delta) out.push(...delta.trace);
    if (clearance) out.push(...clearance.trace);
    if (sectorRank) out.push(...sectorRank.trace);
    if (usgs) out.push(...usgs.trace);
    return out;
  }, [scan, triage, verify, dispatch, delta, clearance, sectorRank, usgs]);

  const canvasDetections: ScanDetection[] = useMemo(() => {
    if (viewMode === "delta" && delta) {
      return delta.delta_detections.map((d) => ({
        concept: `${d.concept} (${d.delta_status})`, kind: d.kind, color: d.color,
        bbox_px: { x1: d.bbox.x_min * 1000, y1: d.bbox.y_min * 1000, x2: d.bbox.x_max * 1000, y2: d.bbox.y_max * 1000 },
        bbox: d.bbox, bbox_xyxy_norm: d.bbox_xyxy_norm, area_fraction: d.area_fraction, mask: null, has_mask: false,
      }));
    }
    return scan?.detections ?? [];
  }, [viewMode, delta, scan]);

  const canvasVisibleConcepts = useMemo(() => {
    if (viewMode !== "delta" || !delta) return visibleConcepts;
    return new Set(delta.delta_detections.map((d) => `${d.concept} (${d.delta_status})`));
  }, [viewMode, delta, visibleConcepts]);

  const verificationById = useMemo(() => {
    const map = new Map<string, { status: "verified" | "rejected"; hazardRatio: number; reasons: string[] }>();
    if (!verify) return map;
    const all = [...(verify.final_verification?.corridor_results ?? []), ...(verify.final_verification?.landing_zone_results ?? [])];
    for (const r of all) map.set(r.candidate_id, { status: r.status, hazardRatio: r.hazard_intersection_ratio, reasons: r.reasons ?? [] });
    return map;
  }, [verify]);

  const corridors: CanvasCorridor[] = useMemo(() => {
    const fromTriage = (triage?.candidate_evacuation_corridors ?? []).map((c) => {
      const v = verificationById.get(c.id);
      return { id: c.id, name: c.name, points: c.points_norm, status: (v?.status ?? "unverified") as CanvasCorridor["status"], hazardRatio: v?.hazardRatio ?? null, detail: v ? v.reasons.join(" ") : c.rationale } as CanvasCorridor;
    });
    if (fromTriage.length) return fromTriage;
    // After a verify-only payload, geometry may live on verified candidate records.
    const recs = [...(verify?.verified_candidates?.corridors ?? [])] as Record<string, unknown>[];
    return recs.filter((r) => Array.isArray(r.points_norm)).map((r) => ({
      id: String(r.id ?? "corridor"), name: String(r.name ?? r.id ?? "Corridor"),
      points: r.points_norm as CanvasCorridor["points"], status: "verified" as const, hazardRatio: null, detail: "Verified candidate record",
    }));
  }, [triage, verify, verificationById]);

  const zones: CanvasZone[] = useMemo(() => {
    const fromTriage = (triage?.candidate_landing_zones ?? []).map((z) => {
      const v = verificationById.get(z.id);
      return { id: z.id, name: z.name, center: z.center_norm, radius: z.radius_norm, status: (v?.status ?? "unverified") as CanvasZone["status"], hazardRatio: v?.hazardRatio ?? null, detail: v ? v.reasons.join(" ") : z.rationale } as CanvasZone;
    });
    if (fromTriage.length) return fromTriage;
    const recs = [...(verify?.verified_candidates?.landing_zones ?? [])] as Record<string, unknown>[];
    return recs.filter((r) => r.center_norm && typeof r.radius_norm === "number").map((r) => ({
      id: String(r.id ?? "zone"), name: String(r.name ?? r.id ?? "Landing zone"),
      center: r.center_norm as CanvasZone["center"], radius: Number(r.radius_norm), status: "verified" as const, hazardRatio: null, detail: "Verified candidate record",
    }));
  }, [triage, verify, verificationById]);

  function setStageState(s: Stage, v: StageState) { setStage((prev) => ({ ...prev, [s]: v })); }
  function fail(s: Stage, e: unknown) { setStageState(s, "error"); setError(e instanceof Error ? e.message : String(e)); }

  function loadImage(file: File | null) {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setImageFile(file);
    setImageUrl(file ? URL.createObjectURL(file) : null);
    setScan(null); setTriage(null); setVerify(null); setDispatch(null); setDispatchBlock(null); setSelected(null);
    setStage({ scan: "idle", triage: "idle", verify: "idle", dispatch: "idle", pipeline: "idle" });
    setError(null);
  }

  async function handleScan() {
    if (!imageFile) { setError("Upload an image first - sam-3.1 needs aerial/drone/street imagery."); return; }
    setStageState("scan", "running"); setError(null);
    try {
      const r = await scanHazards(imageFile);
      setScan(r); setTriage(null); setVerify(null); setDispatch(null); setDispatchBlock(null); setSelected(null);
      setStageState("scan", "done"); setStageState("triage", "idle"); setStageState("verify", "idle"); setStageState("dispatch", "idle");
    } catch (e) { fail("scan", e); }
  }

  async function handleTriage() {
    if (!audioFile && !fieldText.trim()) { setError("Triage needs a field report: type the text fallback or attach a WAV radio recording."); return; }
    setStageState("triage", "running"); setError(null);
    try {
      const r = await triageReport({ audio: audioFile, text: fieldText.trim() || null, scanResult: scan, image: imageFile });
      setTriage(r); setVerify(null); setDispatch(null); setDispatchBlock(null); setSelected(null);
      setStageState("triage", "done"); setStageState("verify", "idle"); setStageState("dispatch", "idle");
    } catch (e) { fail("triage", e); }
  }
  async function handleVerify() {
    if (!scan) { setError("Run STEP 1 - SCAN first. The verifier checks proposals against sam-3.1 hazard boxes."); return; }
    if (!triage && corridors.length === 0 && zones.length === 0) { setError("Run STEP 2 - TRIAGE first so muse-spark-1.3 can propose candidate corridors / landing zones."); return; }
    const lat = latitude.trim() ? Number(latitude) : null;
    const lon = longitude.trim() ? Number(longitude) : null;
    if ((lat == null) !== (lon == null) || (lat != null && (Number.isNaN(lat) || Number.isNaN(lon)))) { setError("Latitude and longitude must be given together (or both left blank). OSM facility lookup is skipped without real coordinates."); return; }
    setStageState("verify", "running"); setError(null);
    try {
      const r = await verifyCandidates({ scan_result: scan, triage_result: triage, latitude: lat, longitude: lon, auto_correct: true, max_correction_attempts: 3 });
      setVerify(r); setDispatch(null); setDispatchBlock(null);
      setStageState("verify", r.dispatch_ready ? "done" : "blocked");
      if (!r.dispatch_ready) setStageState("dispatch", "blocked");
      else setStageState("dispatch", "idle");
    } catch (e) { fail("verify", e); }
  }

  async function handleDispatch() {
    if (!verify) { setError("Run STEP 3 - VERIFY first. muse-wonder-1.0 only ever receives verified candidates."); return; }
    setStageState("dispatch", "running"); setError(null);
    try {
      const r = await runDispatch({ verification_result: verify, triage_result: triage, include_briefing_card: includeCard });
      setDispatch(r); setDispatchBlock(null); setStageState("dispatch", "done");
    } catch (e) { fail("dispatch", e); }
  }

  async function runPipelineCore(img: File, reportText: string, audio: File | null, lat: number | null, lon: number | null) {
    setStage({ scan: "running", triage: "running", verify: "running", dispatch: "running", pipeline: "running" });
    setError(null);
    try {
      const r = await runCrisisGrid({ image: img, audio, text: reportText.trim() || null, latitude: lat, longitude: lon, autoCorrect: true, maxCorrectionAttempts: 3, includeBriefingCard: includeCard });
      setScan(r.scan); setTriage(r.triage); setVerify(r.verification); setDispatch(r.dispatch); setDispatchBlock(r.dispatch_block); setSelected(null);
      setStage({ scan: "done", triage: "done", verify: r.verification.dispatch_ready ? "done" : "blocked", dispatch: r.dispatch ? "done" : "blocked", pipeline: "done" });
    } catch (e) {
      setStage({ scan: "error", triage: "error", verify: "error", dispatch: "error", pipeline: "error" });
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handlePipeline() {
    if (!imageFile) { setError("Upload an image first - the unified pipeline starts with sam-3.1 segmentation."); return; }
    if (!audioFile && !fieldText.trim()) { setError("Add a typed field report (or WAV) - triage fuses the field report with the scan."); return; }
    const lat = latitude.trim() ? Number(latitude) : null;
    const lon = longitude.trim() ? Number(longitude) : null;
    if ((lat == null) !== (lon == null)) { setError("Latitude and longitude must be given together (or both blank)."); return; }
    setActivePresetId(null);
    await runPipelineCore(imageFile, fieldText, audioFile, lat, lon);
  }

  // ---- Global disaster preset handlers ----------------------------------- //
  async function fetchPresetFile(path: string, filename: string, type: string): Promise<File> {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Preset asset ${path} failed to load (${res.status}). Check frontend/public/presets.`);
    const blob = await res.blob();
    return new File([blob], filename, { type: type || blob.type });
  }

  async function applyPreset(preset: CrisisPreset): Promise<{ img: File; audio: File | null }> {
    const img = await fetchPresetFile(preset.image_path, preset.image_filename, "image/jpeg");
    const audio = preset.audio_path ? await fetchPresetFile(preset.audio_path, preset.audio_filename ?? "field-radio.wav", "audio/wav") : null;
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setImageFile(img); setImageUrl(URL.createObjectURL(img));
    setAudioFile(audio); setFieldText(preset.field_report);
    setLatitude(preset.latitude != null ? String(preset.latitude) : "");
    setLongitude(preset.longitude != null ? String(preset.longitude) : "");
    setAfterScan(null); setDelta(null); setClearance(null); setActivePresetId(preset.id);
    return { img, audio };
  }

  async function handleLoadPreset(preset: CrisisPreset) {
    setError(null);
    try { await applyPreset(preset); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function handleRunPreset(preset: CrisisPreset) {
    setError(null);
    try {
      const { img, audio } = await applyPreset(preset);
      await runPipelineCore(img, preset.field_report, audio, preset.latitude, preset.longitude);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function handleSelectTestImage(item: DisasterTestImage, imageOnly = false) {
    setError(null);
    try {
      const img = await fetchPresetFile(item.image_path, item.image_filename, "image/jpeg");
      loadImage(img);
      setActivePresetId(item.id);
      if (!imageOnly) {
        const audio = item.audio_path ? await fetchPresetFile(item.audio_path, item.audio_filename ?? "field-radio.wav", "audio/wav") : null;
        setAudioFile(audio);
        setFieldText(item.field_report);
        setLatitude(String(item.latitude));
        setLongitude(String(item.longitude));
      }
      if (item.after_pair_path && item.after_pair_filename) {
        const afterImg = await fetchPresetFile(item.after_pair_path, item.after_pair_filename, "image/jpeg");
        loadAfterImage(afterImg);
      }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  async function handleFetchUsgs(feed = "4.5_day") {
    setUsgsBusy(true); setError(null);
    try { const r = await fetchUsgsLive(feed, 4.5, 6); setUsgs(r); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setUsgsBusy(false); }
  }

  async function handleLoadUsgsEvent(ev: UsgsEvent, autoRun: boolean) {
    setError(null);
    const eqPreset = presets.find((p) => p.id === ev.recommended_preset_id) ?? presets[1] ?? FALLBACK_PRESETS[1];
    try {
      const img = await fetchPresetFile(eqPreset.image_path, eqPreset.image_filename, "image/jpeg");
      if (imageUrl) URL.revokeObjectURL(imageUrl);
      setImageFile(img); setImageUrl(URL.createObjectURL(img));
      setAudioFile(null); setFieldText(ev.field_report);
      setLatitude(String(ev.latitude)); setLongitude(String(ev.longitude));
      setAfterScan(null); setDelta(null); setClearance(null); setActivePresetId(ev.event_id);
      if (autoRun) await runPipelineCore(img, ev.field_report, null, ev.latitude, ev.longitude);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }


  // ---- Damage delta & multi-sector handlers ----------------------------- //
  function loadAfterImage(file: File | null) {
    if (afterUrl) URL.revokeObjectURL(afterUrl);
    setAfterFile(file); setAfterUrl(file ? URL.createObjectURL(file) : null);
    setAfterScan(null); setDelta(null); setClearance(null); setViewMode("live");
  }

  async function handleScanAfter() {
    if (!afterFile) { setError("Upload an AFTER image first."); return; }
    setDay7Busy(true); setError(null);
    try { const r = await scanHazards(afterFile); setAfterScan(r); setDelta(null); setClearance(null); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setDay7Busy(false); }
  }

  async function handleComputeDelta() {
    if (!scan || !afterScan) { setError("Delta needs both the current (before) scan and a scanned AFTER frame."); return; }
    setDay7Busy(true); setError(null);
    try { const r = await computeDelta(scan, afterScan); setDelta(r); setViewMode("delta"); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setDay7Busy(false); }
  }

  async function handleVerifyClearance() {
    if (!afterScan) { setError("Scan the AFTER frame first."); return; }
    if (!triage && corridors.length === 0 && zones.length === 0) { setError("No candidates to re-verify - run TRIAGE first so the same candidates can be re-checked."); return; }
    setDay7Busy(true); setError(null);
    try {
      const r = await verifyClearance({ scanAfter: afterScan, triageResult: triage, verificationBefore: verify });
      setClearance(r);
      // The ONLY way state flips: deterministic verifier output on the after scan
      // becomes the live verification (and after scan becomes the live field).
      setVerify(r.verification_result); setScan(afterScan); setDispatch(null); setDispatchBlock(null);
      setStageState("verify", r.dispatch_ready ? "done" : "blocked");
      setStageState("dispatch", r.dispatch_ready ? "idle" : "blocked");
      setViewMode("live");
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setDay7Busy(false); }
  }

  function handleSaveSector() {
    if (!scan && !triage) { setError("Nothing to save as a sector yet - run at least a scan."); return; }
    const name = sectorName.trim() || `Sector ${sectorStore.length + 1}`;
    const id = `${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${Date.now().toString(36)}`;
    setSectorStore((prev) => [...prev, { id, name, savedAt: new Date().toLocaleTimeString(), imageUrl, scan, triage, verify }]);
    setSectorName("");
  }

  function handleLoadSector(id: string) {
    const s = sectorStore.find((x) => x.id === id); if (!s) return;
    setScan(s.scan); setTriage(s.triage); setVerify(s.verify);
    setDispatch(null); setDispatchBlock(null); setDelta(null); setClearance(null); setAfterScan(null);
    setImageUrl(s.imageUrl); setViewMode("live"); setSelected(null); setError(null);
  }

  async function handleRankSectors() {
    setDay7Busy(true); setError(null);
    try {
      const payload = sectorStore.map((s) => ({
        sector_id: s.id, name: s.name,
        triage_result: s.triage as unknown as Record<string, unknown> | null,
        verify_result: s.verify as unknown as Record<string, unknown> | null,
        scan_result: s.scan as unknown as Record<string, unknown> | null,
      }));
      setSectorRank(await rankSectors(payload as Record<string, unknown>[]));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setDay7Busy(false); }
  }

  const sectorSnapshots: SectorSnapshot[] = sectorStore.map((s) => ({
    sector_id: s.id, name: s.name, savedAt: s.savedAt,
    hasScan: !!s.scan, hasTriage: !!s.triage, hasVerify: !!s.verify,
    severity: s.triage?.triage.severity ?? null, urgency: s.triage?.triage.urgency_score ?? null,
  }));

  function toggleConcept(c: string) {
    setVisibleConcepts((prev) => { const next = new Set(prev); if (next.has(c)) next.delete(c); else next.add(c); return next; });
  }

  const stageChip = (label: string, s: StageState) => (
    <span className={`stage-chip stage-${s}`}>{label}: {s.toUpperCase()}</span>
  );

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>CRISISGRID</h1>
          <p>AUTONOMOUS DISASTER TRIAGE - INFRASTRUCTURE ASSESSMENT - EMERGENCY DISPATCH</p>
        </div>
        <div className="status-box">
          <div>BACKEND: {backendDown ? "OFFLINE" : health ? `ONLINE (v${health.version.replace(/-day\d+$/i, "")}${health.compute_runtime ? " · " + health.compute_runtime.toUpperCase() : ""})` : "CHECKING..."}</div>
          <div>MODEL_API_KEY: {health ? (keyReady ? "CONFIGURED" : "NOT SET") : "-"}</div>
          <div>API: api.meta.ai/v1 - ONLY INFERENCE PROVIDER</div>
        </div>
      </header>

      {!backendDown && health && !keyReady && (<div className="alert" role="alert">MODEL_API_KEY NOT SET - copy <code>.env.example</code> to <code>.env</code>, set the key, restart the backend. Live model calls stay disabled until then.</div>)}
      {backendDown && (<div className="alert" role="alert">BACKEND OFFLINE - start it with <code>uvicorn backend.main:app --reload --port 8000</code> from the repo root.</div>)}
      {error && (<div className="alert" role="alert">{error} <button type="button" className="alert-close" onClick={() => setError(null)}>DISMISS</button></div>)}

      <div className="model-strip" aria-label="Meta models">
        <span>SAM-3.1 SEGMENT</span><span>MUSE-VOICE-TRANSCRIBE-1.0</span><span>MUSE-SPARK-1.3 TRIAGE</span><span>PYTHON VERIFIER - ONLY GREEN SOURCE</span><span>MUSE-WONDER-1.0 DISPATCH</span><span>MUSE-IMAGE-1.0 BRIEFING</span>
      </div>

      <section className="panel control-panel" aria-label="Mission inputs and pipeline controls">
        <div className="panel-head"><span>MISSION CONTROL</span><span className="tag tag-yellow">AUTONOMOUS PIPELINE</span></div>
        <div className="control-grid">
          <div
            className={`dropzone${dragOver ? " drag" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); loadImage(e.dataTransfer.files?.[0] ?? null); }}
          >
            {imageUrl && <img src={imageUrl} alt="Selected disaster frame" className="dropzone-preview" />}
            <strong>{imageFile ? imageFile.name : "DROP DISASTER IMAGE HERE — OR SELECT A TEST IMAGE BELOW"}</strong>
            <span>{imageFile ? `${(imageFile.size / 1024).toFixed(0)} KB - click below to replace` : "aerial / drone / street - JPG or PNG"}</span>
            <label className="btn btn-file">CHOOSE IMAGE<input type="file" accept="image/*" hidden onChange={(e) => loadImage(e.target.files?.[0] ?? null)} /></label>
          </div>
          <div className="control-fields">
            <label className="field-label" htmlFor="field-report">FIELD REPORT (TEXT FALLBACK - OR ATTACH RADIO WAV)</label>
            <textarea id="field-report" className="field-input control-textarea" rows={3} value={fieldText} onChange={(e) => setFieldText(e.target.value)}
              placeholder="e.g. Bridge out on the north road, water rising, twelve people on rooftops near the market, need boats and a helicopter landing zone." />
            <label className="field-label" htmlFor="audio-file">RADIO AUDIO (WAV, MONO 16K/24K - muse-voice-transcribe-1.0)</label>
            <input id="audio-file" className="field-input" type="file" accept=".wav,audio/wav" onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)} />
            <div className="latlon-row">
              <div><label className="field-label" htmlFor="lat">LATITUDE (OPTIONAL, OSM)</label><input id="lat" className="field-input inline-input" inputMode="decimal" value={latitude} onChange={(e) => setLatitude(e.target.value)} placeholder="e.g. 27.7172" /></div>
              <div><label className="field-label" htmlFor="lon">LONGITUDE (OPTIONAL, OSM)</label><input id="lon" className="field-input inline-input" inputMode="decimal" value={longitude} onChange={(e) => setLongitude(e.target.value)} placeholder="e.g. 85.3240" /></div>
            </div>
          </div>
        </div>
        <div className="sample-strip" aria-label="Built-in disaster test images">
          <div className="sample-head">
            <span>SELECT TEST DISASTER IMAGE ({filteredSamples.length}/9 SCENES — FLOOD · EARTHQUAKE · LANDSLIDE · CYCLONE · TORNADO · WILDFIRE)</span>
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
              {(["all", "flood", "earthquake", "landslide", "cyclone", "tornado", "wildfire", "post-clearance"] as const).map((cat) => (
                <button key={cat} type="button" className={`trace-filter${sampleFilter === cat ? " active" : ""}`} onClick={() => setSampleFilter(cat)}>
                  {cat.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="sample-grid">
            {filteredSamples.map((s) => (
              <div key={s.id} className={`sample-card${activePresetId === s.id ? " active" : ""}`}>
                <div>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={s.image_path} alt={s.name} className="sample-thumb" onClick={() => handleSelectTestImage(s, false)} />
                  <div className="sample-meta">
                    <div>
                      <span className="tag tag-red">{s.category.toUpperCase()}</span>{" "}
                      {s.audio_path && <span className="tag tag-green">WAV</span>}
                    </div>
                    <strong>{s.name}</strong>
                    <small>{s.region}</small>
                  </div>
                </div>
                <div className="sample-actions">
                  <button type="button" className="btn btn-small btn-pipeline" disabled={busy} onClick={() => handleSelectTestImage(s, false)}>
                    LOAD SCENE
                  </button>
                  <button type="button" className="btn btn-small" disabled={busy} title="Load image file only without overwriting field report" onClick={() => handleSelectTestImage(s, true)}>
                    IMG ONLY
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="pipeline-row" role="group" aria-label="Pipeline steps">
          <button type="button" className="btn" disabled={busy} onClick={handleScan}>{stage.scan === "running" ? "SCANNING (9 SAM-3.1 CALLS)..." : "STEP 1 - SCAN"}</button>
          <button type="button" className="btn" disabled={busy} onClick={handleTriage}>{stage.triage === "running" ? "TRIAGING..." : "STEP 2 - TRIAGE"}</button>
          <button type="button" className="btn" disabled={busy} onClick={handleVerify}>{stage.verify === "running" ? "VERIFYING + RE-ROUTING..." : "STEP 3 - VERIFY"}</button>
          <button type="button" className="btn btn-pipeline" disabled={busy} onClick={handlePipeline}>{stage.pipeline === "running" ? "FULL PIPELINE RUNNING (CAN TAKE MINUTES)..." : "RUN FULL PIPELINE - /api/run-crisisgrid"}</button>
        </div>
        <div className="stage-row" aria-live="polite">
          {stageChip("1 SCAN", stage.scan)}{stageChip("2 TRIAGE", stage.triage)}{stageChip("3 VERIFY", stage.verify)}{stageChip("4 DISPATCH", stage.dispatch)}
          {verify && <span className="stage-chip">VERIFIER: {verify.status.toUpperCase()} - {verify.final_verification.summary.verified} VERIFIED / {verify.final_verification.summary.rejected} REJECTED</span>}
          {triage && <span className="stage-chip">TRIAGE: {triage.triage.severity.toUpperCase()} - URGENCY {triage.triage.urgency_score}/100</span>}
        </div>
      </section>
      <div className="grid">
        <div className="main-col">
          <TacticalCanvas imageUrl={viewMode === "delta" && afterUrl ? afterUrl : imageUrl} detections={canvasDetections} corridors={corridors} zones={zones}
            visibleConcepts={canvasVisibleConcepts} showCorridors={showCorridors} showZones={showZones} selected={selected} onInspect={setSelected} />
          <section className="panel" aria-label="Overlay layers">
            <div className="panel-head"><span>OVERLAY LAYERS</span><span className="tag">{visibleConcepts.size}/9 CONCEPTS</span></div>
            <div className="layer-grid">
              <div><h4 className="subhead">CRITICAL HAZARDS (RED)</h4>
                {HAZARDS.map((c) => (<label key={c} className="check-row"><input type="checkbox" checked={visibleConcepts.has(c)} onChange={() => toggleConcept(c)} /> {c}</label>))}
              </div>
              <div><h4 className="subhead">PASSABLE INFRASTRUCTURE (GREEN)</h4>
                {SAFE.map((c) => (<label key={c} className="check-row"><input type="checkbox" checked={visibleConcepts.has(c)} onChange={() => toggleConcept(c)} /> {c}</label>))}
              </div>
              <div><h4 className="subhead">CANDIDATES (VERIFIER COLOURS THEM)</h4>
                <label className="check-row"><input type="checkbox" checked={showCorridors} onChange={(e) => setShowCorridors(e.target.checked)} /> evacuation corridors ({corridors.length})</label>
                <label className="check-row"><input type="checkbox" checked={showZones} onChange={(e) => setShowZones(e.target.checked)} /> landing zones ({zones.length})</label>
                <div className="layer-actions">
                  <button type="button" className="btn btn-small" onClick={() => setVisibleConcepts(new Set(ALL_CONCEPTS))}>SHOW ALL</button>
                  <button type="button" className="btn btn-small" onClick={() => setVisibleConcepts(new Set())}>HIDE ALL</button>
                </div>
              </div>
            </div>
            {scan && <p className="panel-note">Scan: {scan.summary.total_detections} detections / {scan.summary.total_masks} masks across {scan.summary.concepts_succeeded}/9 concepts in {Math.round(scan.summary.total_latency_ms)} ms. Status stays <strong>UNVERIFIED SEGMENTATION ONLY</strong> until the deterministic geometry verifier rules on routes.</p>}
          </section>

          {triage && (
            <section className="panel" aria-label="Triage summary">
              <div className="panel-head"><span>TRIAGE - muse-spark-1.3</span><span className="tag tag-yellow">{triage.triage.severity.toUpperCase()} - {triage.triage.urgency_score}/100</span></div>
              <p className="panel-note"><strong>{triage.triage.incident_type}:</strong> {triage.triage.summary}</p>
              <p className="panel-note"><strong>Transcript ({triage.input.source.replace("_", " ")}):</strong> {triage.transcript || "(no transcript)"}</p>
              <p className="panel-note"><strong>People at risk:</strong> {triage.triage.people_at_risk.count_estimate ?? "unknown"} - {triage.triage.people_at_risk.description}</p>
              <h4 className="subhead pad">RANKED PRIORITIES (PROPOSALS - NOT ORDERS)</h4>
              <ol className="phase-list pad-list">
                {triage.triage.priorities.map((pr) => (<li key={pr.rank}><strong>#{pr.rank} {pr.category}:</strong> {pr.action} <small>({pr.rationale})</small></li>))}
              </ol>
              <p className="panel-note">Candidates proposed: {corridors.length} corridor(s), {zones.length} landing zone(s) - all YELLOW until deterministic Python verification. Missing info: {triage.triage.missing_information.join("; ") || "none declared"}.</p>
              {verify && <p className="panel-note"><strong>Verifier verdict:</strong> {verify.status.toUpperCase()} - dispatch ready: {verify.dispatch_ready ? "YES" : "NO"}. Correction attempts used: {verify.correction.attempts_used}/{verify.correction.max_attempts} ({verify.correction.status}). Facilities (OSM): {verify.emergency_facilities.status} - {verify.emergency_facilities.facilities.slice(0, 5).map((f) => `${f.name} (${f.type}, ${Math.round(f.distance_m)} m)`).join("; ") || "none / not queried"}</p>}
            </section>
          )}
        </div>
        <div className="side">
          <AgentTrace entries={trace} />
          <DispatchConsole dispatch={dispatch} dispatchBlock={dispatchBlock} verify={verify} running={stage.dispatch === "running"}
            canDispatch={!!verify?.dispatch_ready} onDispatch={handleDispatch} includeCard={includeCard} onIncludeCardChange={setIncludeCard} />
        </div>
      </div>

      <div style={{ marginTop: 18 }}>
        <PresetPanel presets={presets} busy={busy || day7Busy} activeId={activePresetId} source={presetSource}
          onRun={handleRunPreset} onLoad={handleLoadPreset} usgs={usgs} usgsBusy={usgsBusy} onFetchUsgs={handleFetchUsgs} onLoadUsgsEvent={handleLoadUsgsEvent} />
      </div>

      <div className="day7-grid">
        <DeltaPanel hasBefore={!!scan} afterName={afterFile?.name ?? null} afterScanDone={!!afterScan}
          delta={delta} clearance={clearance} viewMode={viewMode} busy={day7Busy || busy}
          onAfterImage={loadAfterImage} onScanAfter={handleScanAfter} onComputeDelta={handleComputeDelta}
          onVerifyClearance={handleVerifyClearance} onViewMode={setViewMode} />
        <SectorPanel sectors={sectorSnapshots} rank={sectorRank} busy={day7Busy}
          name={sectorName} onName={setSectorName} onSave={handleSaveSector} onRank={handleRankSectors}
          onLoad={handleLoadSector} onDelete={(id) => setSectorStore((prev) => prev.filter((s) => s.id !== id))}
          canSave={!!scan || !!triage} />
      </div>

      <footer className="footer">CRISISGRID TACTICAL COMMAND · POWERED BY META MODEL API (api.meta.ai/v1) · MODELS PROPOSE, DETERMINISTIC PYTHON VERIFIES, ONLY VERIFIED ROUTES DISPATCH</footer>
    </main>
  );
}
