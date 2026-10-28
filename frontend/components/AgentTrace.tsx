"use client";
// Day 6: Live Verifiable Agent Trace - every proposal, verification, rejection
// and re-route from scan/triage/verify/dispatch, in arrival order. Read-only audit log.
import { useEffect, useRef, useState } from "react";
import type { ScanTraceEntry } from "@/lib/api";

type Filter = "all" | "verified" | "rejected" | "caution";

function normState(s: string): "verified" | "rejected" | "caution" | "info" {
  if (s === "verified") return "verified";
  if (s === "rejected") return "rejected";
  if (s === "caution" || s === "pending") return "caution";
  return "info";
}

export default function AgentTrace({ entries }: { entries: ScanTraceEntry[] }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [follow, setFollow] = useState(true);
  const listRef = useRef<HTMLOListElement>(null);

  const counts = {
    verified: entries.filter((e) => normState(e.state) === "verified").length,
    rejected: entries.filter((e) => normState(e.state) === "rejected").length,
    caution: entries.filter((e) => normState(e.state) === "caution").length,
  };
  const shown = filter === "all" ? entries : entries.filter((e) => normState(e.state) === filter);

  useEffect(() => {
    if (follow && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [shown.length, follow]);

  return (
    <section className="panel" aria-label="Verifiable agent trace">
      <div className="panel-head"><span>VERIFIABLE AGENT TRACE</span><span className="tag">{entries.length} EVENTS</span></div>
      <div className="trace-controls" role="group" aria-label="Trace filter">
        {(["all", "verified", "rejected", "caution"] as Filter[]).map((f) => (
          <button key={f} type="button" className={`trace-filter${filter === f ? " active" : ""}`} onClick={() => setFilter(f)} aria-pressed={filter === f}>
            {f.toUpperCase()}{f !== "all" ? ` (${counts[f]})` : ""}
          </button>
        ))}
        <label className="trace-follow"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> AUTO-SCROLL</label>
      </div>
      {entries.length === 0 ? (
        <p className="panel-note">No events yet. Run SCAN, TRIAGE, VERIFY or the full pipeline - every model proposal, deterministic proof, rejection and forced re-route will appear here with its reason. Only events marked VERIFIED are safe to act on.</p>
      ) : (
        <ol className="trace trace-live" ref={listRef}>
          {shown.map((e, i) => {
            const st = normState(e.state);
            return (
              <li key={`${i}-${e.step}-${e.event}`} className={`trace-${st === "caution" ? "pending" : st}`}>
                <strong>{e.step} - {e.event}</strong>
                <span>{e.detail}</span>
                <small className="trace-meta">
                  state: {st.toUpperCase()}
                  {e.concept ? ` - concept: ${e.concept}` : ""}
                  {e.latency_ms != null ? ` - ${Math.round(e.latency_ms)} ms` : ""}
                  {(e as { candidate_id?: string }).candidate_id ? ` - candidate: ${(e as { candidate_id?: string }).candidate_id}` : ""}
                </small>
              </li>
            );
          })}
        </ol>
      )}
      <p className="panel-note">Trust rule: green VERIFIED events come only from deterministic local Python (<code>verifiable_corridor_engine.py</code>). Yellow = unverified model proposal. Red = rejected with geometric evidence.</p>
    </section>
  );
}
