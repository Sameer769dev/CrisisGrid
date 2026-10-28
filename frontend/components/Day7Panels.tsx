"use client";
// Before/After Damage Delta + post-clearance re-verification,
// and Multi-Sector Triage ranking. Both engines are deterministic Python with
// zero model calls; a blocked corridor flips green only via the deterministic geometry
// verifier re-run on the AFTER scan (handled in page state).
import type { ClearanceResult, DeltaResult, SectorRankResult } from "@/lib/api";

export interface SectorSnapshot {
  sector_id: string; name: string; savedAt: string;
  hasScan: boolean; hasTriage: boolean; hasVerify: boolean;
  severity: string | null; urgency: number | null;
}

interface DeltaProps {
  hasBefore: boolean; afterName: string | null; afterScanDone: boolean;
  delta: DeltaResult | null; clearance: ClearanceResult | null;
  viewMode: "live" | "delta"; busy: boolean;
  onAfterImage: (f: File | null) => void; onScanAfter: () => void;
  onComputeDelta: () => void; onVerifyClearance: () => void;
  onViewMode: (m: "live" | "delta") => void;
}

export function DeltaPanel(p: DeltaProps) {
  const d = p.delta;
  return (
    <section className="panel" aria-label="Before after damage delta">
      <div className="panel-head"><span>BEFORE / AFTER DAMAGE DELTA</span><span className="tag tag-yellow">DETERMINISTIC ENGINE · 0 MODEL CALLS</span></div>
      <p className="panel-note">BEFORE = the current scan on the tactical map. Upload the AFTER frame (post-disaster, or post-debris-clearance), scan it, then compare. The delta highlights change only - it <strong>never</strong> verifies a route.</p>
      <div className="delta-controls">
        <label className="btn btn-file">AFTER IMAGE<input type="file" accept="image/*" hidden onChange={(e) => p.onAfterImage(e.target.files?.[0] ?? null)} /></label>
        <span className="delta-after-name">{p.afterName ?? "no after image"}</span>
        <button type="button" className="btn" disabled={p.busy || !p.afterName} onClick={p.onScanAfter}>SCAN AFTER (sam-3.1)</button>
        <button type="button" className="btn" disabled={p.busy || !p.hasBefore || !p.afterScanDone} onClick={p.onComputeDelta}>COMPUTE DELTA</button>
        <button type="button" className="btn btn-pipeline" disabled={p.busy || !p.afterScanDone} onClick={p.onVerifyClearance}>VERIFY CLEARANCE ON AFTER SCAN</button>
      </div>
      <div className="delta-controls" role="group" aria-label="Canvas view mode">
        <button type="button" className={`trace-filter${p.viewMode === "live" ? " active" : ""}`} onClick={() => p.onViewMode("live")} aria-pressed={p.viewMode === "live"}>CANVAS: LIVE SCAN</button>
        <button type="button" className={`trace-filter${p.viewMode === "delta" ? " active" : ""}`} disabled={!d} onClick={() => p.onViewMode("delta")} aria-pressed={p.viewMode === "delta"}>CANVAS: DELTA VIEW</button>
        {d && <span className="stage-chip">VERDICT: {d.verdict.replaceAll("_", " ").toUpperCase()}</span>}
      </div>
      {d && (
        <div className="dispatch-body">
          <div className="unit-counts">
            <span className="tag tag-red">{d.summary.new_hazards} NEW HAZARDS</span>
            <span className="tag tag-green">{d.summary.cleared_hazards} CLEARED HAZARDS</span>
            <span className="tag">{d.summary.persistent_hazards} PERSISTENT HAZARDS</span>
            <span className="tag tag-red">{d.summary.lost_safe} LOST PASSABLE</span>
            <span className="tag tag-green">{d.summary.new_safe} NEW PASSABLE</span>
          </div>
          <p className="panel-note">Hazard box area {(d.summary.hazard_area_before * 100).toFixed(1)}% -&gt; {(d.summary.hazard_area_after * 100).toFixed(1)}% of frame; passable {(d.summary.safe_area_before * 100).toFixed(1)}% -&gt; {(d.summary.safe_area_after * 100).toFixed(1)}%. Delta view: NEW hazards red, CLEARED hazards green, LOST roads red, persistent hazards yellow.</p>
          {d.warnings.map((w, i) => <p key={i} className="panel-note"><strong>Warning:</strong> {w}</p>)}
          <div className="table-wrap"><table className="unit-table">
            <thead><tr><th>CONCEPT</th><th>BEFORE</th><th>AFTER</th><th>PERSIST</th><th>NEW</th><th>CLEARED/LOST</th><th>AREA Δ</th></tr></thead>
            <tbody>{d.per_concept.map((c) => (
              <tr key={c.concept}><td>{c.concept}</td><td>{c.before_count}</td><td>{c.after_count}</td><td>{c.persistent}</td><td>{c.new}</td><td>{c.cleared}</td>
                <td>{(c.box_area_fraction_delta * 100).toFixed(1)}%</td></tr>))}
            </tbody></table></div>
        </div>
      )}
      {p.clearance && (
        <div className="dispatch-body">
          <h4 className="subhead">POST-CLEARANCE RE-VERIFICATION (DETERMINISTIC GEOMETRY VERIFIER ON AFTER SCAN)</h4>
          <p className="panel-note">Verdict: <strong>{p.clearance.verdict.replaceAll("_", " ").toUpperCase()}</strong> - flipped to verified: [{p.clearance.flipped_to_verified.join(", ") || "none"}]; still blocked: [{p.clearance.still_blocked.join(", ") || "none"}]. Main map + dispatch state now use the AFTER verification.</p>
          <div className="table-wrap"><table className="unit-table">
            <thead><tr><th>CANDIDATE</th><th>BEFORE</th><th>AFTER</th><th>HAZARD BEFORE</th><th>HAZARD AFTER</th><th>FLIP</th></tr></thead>
            <tbody>{p.clearance.status_changes.map((c) => (
              <tr key={c.candidate_id} className={c.flipped_to_verified ? "row-dispatched" : c.after_status === "rejected" ? "row-held" : ""}>
                <td>{c.candidate_id}</td><td>{c.before_status}</td><td>{c.after_status}</td>
                <td>{c.before_hazard_intersection_ratio != null ? `${(c.before_hazard_intersection_ratio * 100).toFixed(1)}%` : "-"}</td>
                <td>{c.after_hazard_intersection_ratio != null ? `${(c.after_hazard_intersection_ratio * 100).toFixed(1)}%` : "-"}</td>
                <td>{c.flipped_to_verified ? "BLOCKED -> VERIFIED" : c.flipped_to_rejected ? "VERIFIED -> REJECTED" : "-"}</td></tr>))}
            </tbody></table></div>
        </div>
      )}
    </section>
  );
}

interface SectorProps {
  sectors: SectorSnapshot[]; rank: SectorRankResult | null; busy: boolean;
  name: string; onName: (v: string) => void;
  onSave: () => void; onRank: () => void;
  onLoad: (id: string) => void; onDelete: (id: string) => void;
  canSave: boolean;
}

export function SectorPanel(p: SectorProps) {
  return (
    <section className="panel" aria-label="Multi sector triage">
      <div className="panel-head"><span>MULTI-SECTOR TRIAGE</span><span className="tag tag-yellow">DETERMINISTIC PRIORITY MATRIX</span></div>
      <p className="panel-note">Save each scanned sector, then rank all sectors for dispatch priority. Score = urgency x0.40 + severity (max 25) + people (max 15) + hazard footprint (max 10) + access pressure (max 10). Ranking orders work - dispatch still requires geometrically verified candidates in that sector.</p>
      <div className="delta-controls">
        <input className="field-input inline-input sector-name" value={p.name} onChange={(e) => p.onName(e.target.value)} placeholder="Sector name (e.g. Old Town)" aria-label="Sector name" />
        <button type="button" className="btn" disabled={!p.canSave} onClick={p.onSave}>SAVE CURRENT AS SECTOR</button>
        <button type="button" className="btn btn-pipeline" disabled={p.busy || p.sectors.length === 0} onClick={p.onRank}>RANK SECTORS</button>
      </div>
      {p.sectors.length === 0 ? <p className="panel-note">No sectors saved yet. Run scan/triage/verify on the map above, name it, and save it here.</p> : (
        <ul className="plain-list sector-list">
          {p.sectors.map((s) => (
            <li key={s.sector_id}><strong>{s.name}</strong> <small>({s.savedAt}) scan:{s.hasScan ? "Y" : "N"} triage:{s.hasTriage ? "Y" : "N"} verify:{s.hasVerify ? "Y" : "N"}{s.severity ? ` ${s.severity}/${s.urgency ?? "-"}` : ""}</small>{" "}
              <button type="button" className="btn btn-small" onClick={() => p.onLoad(s.sector_id)}>LOAD</button>{" "}
              <button type="button" className="btn btn-small" onClick={() => p.onDelete(s.sector_id)}>DELETE</button></li>
          ))}
        </ul>
      )}
      {p.rank && (
        <div className="dispatch-body">
          <div className="table-wrap"><table className="unit-table">
            <thead><tr><th>#</th><th>SECTOR</th><th>SCORE</th><th>BREAKDOWN (U/S/P/H/A)</th><th>ACTION</th></tr></thead>
            <tbody>{p.rank.ranked_sectors.map((r) => (
              <tr key={r.sector_id}><td>{r.rank}</td><td><strong>{r.name}</strong><br /><small>{r.severity} - urgency {r.urgency_score} - people {r.people_at_risk ?? "?"} - verified {r.candidates_verified}/{r.candidates_total}</small></td>
                <td><strong>{r.score}</strong></td>
                <td>{r.breakdown.urgency_component}/{r.breakdown.severity_component}/{r.breakdown.people_component}/{r.breakdown.hazard_component}/{r.breakdown.access_component}<br /><small>{r.breakdown.access_note}</small></td>
                <td>{r.recommended_action.replaceAll("_", " ").toUpperCase()}</td></tr>))}
            </tbody></table></div>
          <p className="panel-note">{p.rank.next_step}</p>
        </div>
      )}
    </section>
  );
}
