"use client";
// Day 8: 1-click global disaster presets. A preset bundles imagery + field
// report only; RUN executes the full live pipeline (Days 2-5) exactly like a
// manual upload. Failures surface through the page error banner - a preset
// can honestly end rejected / completed_no_dispatch.
import type { CrisisPreset } from "@/lib/presets";

interface Props {
  presets: CrisisPreset[]; busy: boolean; activeId: string | null;
  source: "api" | "fallback";
  onRun: (p: CrisisPreset) => void; onLoad: (p: CrisisPreset) => void;
}

export default function PresetPanel(p: Props) {
  return (
    <section className="panel" aria-label="Global disaster presets">
      <div className="panel-head"><span>GLOBAL DISASTER PRESETS - 1-CLICK JUDGE TESTING</span>
        <span className="tag tag-yellow">DAY 8 - {p.source === "api" ? "LIVE CATALOGUE" : "OFFLINE FALLBACK"}</span></div>
      <p className="panel-note">Each preset loads real pipeline inputs only (image + field report{`{audio where available}`}). Nothing is pre-baked: sam-3.1 segments live, Spark proposes, deterministic Python verifies, and Wonder dispatches only on verified geometry. Generated demo scenes are labelled as such.</p>
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
              <p><small><strong>Judge watch:</strong> {preset.judge_hint}</small></p>
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
    </section>
  );
}
