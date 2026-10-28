"use client";
// Global disaster scenarios: 1-click tactical presets + Live USGS Seismic Telemetry.
// Presets and USGS events bundle real disaster inputs (imagery + field report + coordinates)
// ONLY; running one executes the full live pipeline (scan -> triage -> verify -> dispatch).
import type { UsgsEvent, UsgsLiveResult } from "@/lib/api";
import type { CrisisPreset } from "@/lib/presets";

interface Props {
  presets: CrisisPreset[];
  busy: boolean;
  activeId: string | null;
  source: "api" | "fallback";
  onRun: (p: CrisisPreset) => void;
  onLoad: (p: CrisisPreset) => void;
  usgs?: UsgsLiveResult | null;
  usgsBusy?: boolean;
  onFetchUsgs?: (feed: string) => void;
  onLoadUsgsEvent?: (ev: UsgsEvent, autoRun: boolean) => void;
}

export default function PresetPanel(p: Props) {
  return (
    <section className="panel" aria-label="Global disaster presets">
      <div className="panel-head">
        <span>GLOBAL DISASTER SCENARIOS — 1-CLICK TACTICAL PRESETS</span>
        <span className="tag tag-yellow">{p.source === "api" ? "LIVE SCENARIO CATALOGUE" : "BUILT-IN CATALOGUE"}</span>
      </div>
      <p className="panel-note">
        Each preset loads real pipeline inputs only (imagery + emergency radio audio or field report). Nothing is pre-baked: sam-3.1 segments live, Spark proposes, deterministic Python verifies, and Wonder dispatches only on verified geometry. Generated demo scenes are labelled as such.
      </p>
      <div className="preset-cards">
        {p.presets.map((preset) => (
          <article key={preset.id} className={`preset-card${p.activeId === preset.id ? " active" : ""}`}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preset.image_path} alt={`${preset.name} preset scene`} className="preset-thumb" />
            <div className="preset-body">
              <strong>{preset.name.toUpperCase()}</strong>
              <span className="tag">{preset.disaster_type.toUpperCase()}</span>
              <p>{preset.description}</p>
              <p><small><strong>Focus:</strong> {preset.expected_focus.join(", ")}</small></p>
              <p><small><strong>Tactical focus:</strong> {preset.judge_hint}</small></p>
              <p><small>{preset.image_provenance}{preset.audio_path ? " Includes field-radio WAV." : " Text report fallback."}</small></p>
              <div className="preset-actions">
                <button type="button" className="btn btn-pipeline" disabled={p.busy} onClick={() => p.onRun(preset)}>
                  {p.activeId === preset.id && p.busy ? "RUNNING PIPELINE..." : "RUN PRESET - FULL PIPELINE"}
                </button>
                <button type="button" className="btn" disabled={p.busy} onClick={() => p.onLoad(preset)}>LOAD ONLY</button>
              </div>
            </div>
          </article>
        ))}
      </div>

      {p.onFetchUsgs && (
        <div className="dispatch-body" style={{ borderTop: "4px solid #111", paddingTop: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
            <div>
              <strong>LIVE USGS SEISMIC TELEMETRY (earthquake.usgs.gov · 0 MODEL CALLS)</strong>
              <p className="panel-note" style={{ padding: "4px 0 0" }}>
                Pull real-time global earthquakes from the official USGS GeoJSON feed and inject their live epicenter coordinates (for OpenStreetMap Overpass hospital/shelter lookup) and sensor telemetry into Mission Control.
              </p>
            </div>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <button type="button" className="btn btn-small" disabled={p.busy || p.usgsBusy} onClick={() => p.onFetchUsgs?.("4.5_day")}>
                {p.usgsBusy ? "QUERYING USGS..." : "FETCH LIVE M4.5+ (PAST 24H)"}
              </button>
              <button type="button" className="btn btn-small" disabled={p.busy || p.usgsBusy} onClick={() => p.onFetchUsgs?.("significant_month")}>
                SIGNIFICANT EVENTS (30D)
              </button>
            </div>
          </div>

          {p.usgs && (
            <div style={{ marginTop: "10px" }}>
              <div className="unit-counts">
                <span className="tag tag-green">{p.usgs.count} LIVE USGS EVENTS LOADED</span>
                <span className="tag">FEED: {p.usgs.feed.toUpperCase()}</span>
                <span className="tag">LATENCY: {Math.round(p.usgs.latency_ms)} MS</span>
              </div>
              {p.usgs.events.length === 0 ? (
                <p className="panel-note">No earthquakes matching M&gt;={p.usgs.min_magnitude} in this USGS window. Try SIGNIFICANT EVENTS (30D).</p>
              ) : (
                <div className="table-wrap">
                  <table className="unit-table">
                    <thead>
                      <tr>
                        <th>MAG</th>
                        <th>EPICENTER / PLACE</th>
                        <th>DEPTH</th>
                        <th>COORDINATES (OSM)</th>
                        <th>SEVERITY / ALERT</th>
                        <th>ACTION</th>
                      </tr>
                    </thead>
                    <tbody>
                      {p.usgs.events.map((ev) => (
                        <tr key={ev.event_id} className={ev.severity_estimate === "critical" ? "row-held" : ""}>
                          <td><strong>M{ev.magnitude?.toFixed(1) ?? "?"}</strong></td>
                          <td>
                            <strong>{ev.place}</strong>
                            <br />
                            <small>{ev.time_iso ? new Date(ev.time_iso).toUTCString() : ev.event_id}{ev.tsunami_warning ? " · TSUNAMI ADVISORY" : ""}</small>
                          </td>
                          <td>{ev.depth_km != null ? `${ev.depth_km} km` : "-"}</td>
                          <td>{ev.latitude}, {ev.longitude}</td>
                          <td>
                            <span className={`tag ${ev.severity_estimate === "critical" ? "tag-red" : ev.severity_estimate === "high" ? "tag-yellow" : ""}`}>
                              {ev.severity_estimate.toUpperCase()} ({ev.urgency_estimate}/100)
                            </span>
                          </td>
                          <td>
                            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                              <button type="button" className="btn btn-small" disabled={p.busy} onClick={() => p.onLoadUsgsEvent?.(ev, false)}>
                                LOAD EPICENTER
                              </button>
                              <button type="button" className="btn btn-small btn-pipeline" disabled={p.busy} onClick={() => p.onLoadUsgsEvent?.(ev, true)}>
                                RUN PIPELINE
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
