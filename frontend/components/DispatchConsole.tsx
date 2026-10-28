"use client";
// Dispatch Action Console - muse-wonder-1.0 units (verified targets only),
// deterministic guardrail holds, phases, safety brief and muse-image-1.0 briefing card.
// Held units stay YELLOW with the guardrail reason; nothing unverified is shown as dispatched.
import type { DispatchResult, VerifyResult } from "@/lib/api";

interface Props {
  dispatch: DispatchResult | null;
  dispatchBlock: { status: string; message: string } | null;
  verify: VerifyResult | null;
  running: boolean;
  canDispatch: boolean;
  onDispatch: () => void;
  includeCard: boolean;
  onIncludeCardChange: (v: boolean) => void;
}

export default function DispatchConsole(p: Props) {
  const d = p.dispatch;
  const plan = d?.dispatch;
  const armed = !!plan && (plan.summary_counts?.units_dispatched ?? 0) > 0;

  return (
    <section className="panel" aria-label="Dispatch action console">
      <div className="panel-head"><span>DISPATCH ACTION CONSOLE</span>
        <span className={`tag ${armed ? "" : "tag-red"}`}>{armed ? "ARMED - VERIFIED" : "NOT ARMED"}</span></div>

      <div className="dispatch-actions">
        <button type="button" className="btn btn-dispatch" disabled={!p.canDispatch || p.running} onClick={p.onDispatch}>
          {p.running ? "WONDER REASONING (HIGH EFFORT)..." : "STEP 4 - DISPATCH (muse-wonder-1.0)"}
        </button>
        <label className="check-row"><input type="checkbox" checked={p.includeCard} onChange={(e) => p.onIncludeCardChange(e.target.checked)} /> Generate muse-image-1.0 briefing card</label>
      </div>

      {!p.verify && <p className="panel-note">Locked until STEP 3 verifies at least one corridor or landing zone. Wonder receives <strong>verified candidates only</strong>; rejected IDs are listed as excluded and can never receive a unit.</p>}
      {p.verify && !d && !p.dispatchBlock && (
        <p className="panel-note">Verification status: <strong>{p.verify.status.toUpperCase()}</strong> - dispatch ready: <strong>{p.verify.dispatch_ready ? "YES" : "NO"}</strong>. {p.verify.dispatch_ready ? "Press STEP 4 to generate the multi-unit protocol." : "No verified candidate survived the verifier, so dispatch stays locked. Read the red trace events for the rejection evidence."}</p>
      )}
      {p.dispatchBlock && <div className="alert alert-inline" role="alert">{p.dispatchBlock.message}</div>}

      {d && plan && (
        <div className="dispatch-body">
          <h3 className="dispatch-title">{plan.operation_name}</h3>
          <p className="panel-note">{plan.command_summary}</p>
          <p className="panel-note"><strong>Situation:</strong> {plan.situation_assessment}</p>
          <div className="unit-counts">
            <span className="tag">{plan.summary_counts.units_total} UNITS</span>
            <span className="tag tag-green">{plan.summary_counts.units_dispatched} DISPATCHED</span>
            <span className="tag tag-yellow">{plan.summary_counts.units_held} HELD</span>
            <span className="tag">CONFIDENCE {Math.round((plan.confidence ?? 0) * 100)}%</span>
          </div>
          <div className="table-wrap"><table className="unit-table">
            <thead><tr><th>UNIT</th><th>TYPE</th><th>TASK</th><th>TARGET</th><th>PRI</th><th>ETA</th><th>STATUS</th></tr></thead>
            <tbody>
              {plan.units.map((u) => (
                <tr key={u.unit_id} className={u.dispatch_status === "held" ? "row-held" : "row-dispatched"}>
                  <td><strong>{u.unit_id}</strong><br /><small>{u.staging}</small></td>
                  <td>{u.unit_type}</td><td>{u.task}<br /><small>{u.rationale}</small></td>
                  <td>{u.target_candidate_id ?? "-"}<br /><small>{u.target_kind}</small>
                    {u.requested_target_candidate_id && u.requested_target_candidate_id !== u.target_candidate_id ? <><br /><small>requested: {u.requested_target_candidate_id} (stripped by guardrail)</small></> : null}
                    {u.guardrail_flags?.length ? <><br /><small>guardrail: {u.guardrail_flags.join(", ")}</small></> : null}</td>
                  <td>{u.priority_rank ?? "-"}</td><td>{u.eta_minutes_estimate != null ? `${u.eta_minutes_estimate}m` : "-"}</td>
                  <td><span className={`tag ${u.dispatch_status === "dispatched" ? "tag-green" : "tag-yellow"}`}>{u.dispatch_status.toUpperCase()}</span></td>
                </tr>
              ))}
            </tbody></table></div>

          {plan.phases?.length > 0 && (<><h4 className="subhead">PHASES</h4><ol className="phase-list">{plan.phases.map((ph) => <li key={ph.phase}><strong>Phase {ph.phase} - {ph.name}:</strong> {ph.actions.join("; ")}</li>)}</ol></>)}
          {plan.safety_brief?.length > 0 && (<><h4 className="subhead">SAFETY BRIEF</h4><ul className="plain-list">{plan.safety_brief.map((s, i) => <li key={i}>{s}</li>)}</ul></>)}
          {plan.communications_plan && <p className="panel-note"><strong>Comms:</strong> {plan.communications_plan}</p>}
          {d.guardrail?.actions?.length > 0 && (<><h4 className="subhead">DETERMINISTIC GUARDRAIL (PYTHON, 0 MODEL CALLS)</h4><ul className="plain-list">{d.guardrail.actions.map((a, i) => <li key={i}><strong>{a.unit_id}</strong> - {a.action}: {a.detail}</li>)}</ul></>)}
          <p className="panel-note">Basis: verified corridors [{d.input_basis.verified_corridors.join(", ") || "none"}] / landing zones [{d.input_basis.verified_landing_zones.join(", ") || "none"}] - excluded rejected: [{d.input_basis.excluded_rejected_candidate_ids.join(", ") || "none"}]</p>

          <h4 className="subhead">TACTICAL BRIEFING CARD (muse-image-1.0)</h4>
          {d.briefing_card?.status === "ok" && d.briefing_card.image_base64 ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className="briefing-card" src={`data:image/png;base64,${d.briefing_card.image_base64}`} alt="muse-image-1.0 tactical briefing card generated from verified facts only" />
          ) : d.briefing_card?.status === "ok" && d.briefing_card.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className="briefing-card" src={d.briefing_card.image_url} alt="muse-image-1.0 tactical briefing card generated from verified facts only" />
          ) : d.briefing_card ? (
            <p className="panel-note">Briefing card failed honestly ({d.briefing_card.error?.message ?? "unknown error"}). No card was fabricated; the unit protocol above still stands on verified data.</p>
          ) : <p className="panel-note">No briefing card requested for this run.</p>}
        </div>
      )}
    </section>
  );
}
