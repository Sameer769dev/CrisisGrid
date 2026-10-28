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
  const cleanOperationName = plan?.operation_name
    ? plan.operation_name.replace(/\s*[-–—]?\s*\bday\s*\d+\b/gi, "").trim() || "Verified Emergency Dispatch"
    : "";

  return (
    <section className="panel dispatch-panel" aria-label="Dispatch action console">
      <div className="panel-head">
        <span>DISPATCH ACTION CONSOLE — muse-wonder-1.0</span>
        <span className={`tag ${armed ? "tag-green" : "tag-red"}`}>{armed ? "ARMED - VERIFIED" : "NOT ARMED"}</span>
      </div>

      <div className="dispatch-actions-bar">
        <button type="button" className="btn btn-dispatch" disabled={!p.canDispatch || p.running} onClick={p.onDispatch}>
          {p.running ? "WONDER REASONING (HIGH EFFORT)..." : "STEP 4 - DISPATCH (muse-wonder-1.0)"}
        </button>
        <label className="check-row">
          <input type="checkbox" checked={p.includeCard} onChange={(e) => p.onIncludeCardChange(e.target.checked)} />
          Generate muse-image-1.0 tactical briefing card
        </label>
      </div>

      {!p.verify && (
        <p className="panel-note">
          Locked until STEP 3 verifies at least one corridor or landing zone. Wonder receives <strong>verified candidates only</strong>; rejected IDs are listed as excluded and can never receive a unit.
        </p>
      )}
      {p.verify && !d && !p.dispatchBlock && (
        <p className="panel-note">
          Verification status: <strong>{p.verify.status.toUpperCase()}</strong> — dispatch ready: <strong>{p.verify.dispatch_ready ? "YES" : "NO"}</strong>.{" "}
          {p.verify.dispatch_ready
            ? "Press STEP 4 to generate the multi-unit protocol."
            : "No verified candidate survived the verifier, so dispatch stays locked. Read the red trace events for the rejection evidence."}
        </p>
      )}
      {p.dispatchBlock && <div className="alert alert-inline" role="alert">{p.dispatchBlock.message}</div>}

      {d && plan && (
        <div className="dispatch-body">
          <div className="dispatch-header-row">
            <h3 className="dispatch-title">{cleanOperationName}</h3>
            <div className="unit-counts">
              <span className="tag">{plan.summary_counts.units_total} UNITS</span>
              <span className="tag tag-green">{plan.summary_counts.units_dispatched} DISPATCHED</span>
              <span className="tag tag-yellow">{plan.summary_counts.units_held} HELD</span>
              <span className="tag">CONFIDENCE {Math.round((plan.confidence ?? 0) * 100)}%</span>
            </div>
          </div>

          <div className="dispatch-summary-grid">
            <div className="summary-card">
              <div className="summary-card-label">COMMANDER SUMMARY</div>
              <p>{plan.command_summary}</p>
            </div>
            <div className="summary-card">
              <div className="summary-card-label">VERIFIED SITUATION ASSESSMENT</div>
              <p>{plan.situation_assessment}</p>
            </div>
          </div>

          <div className="table-wrap">
            <table className="unit-table">
              <thead>
                <tr>
                  <th className="col-unit">UNIT &amp; STAGING</th>
                  <th className="col-type">TYPE</th>
                  <th className="col-task">TASK &amp; RATIONALE</th>
                  <th className="col-target">VERIFIED TARGET</th>
                  <th className="col-pri">PRI / ETA</th>
                  <th className="col-status">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {plan.units.map((u) => (
                  <tr key={u.unit_id} className={u.dispatch_status === "held" ? "row-held" : "row-dispatched"}>
                    <td className="col-unit">
                      <strong className="unit-id-badge">{u.unit_id.toUpperCase()}</strong>
                      {u.staging && <div className="unit-sub">Staging: {u.staging}</div>}
                    </td>
                    <td className="col-type">
                      <span className="tag">{u.unit_type.toUpperCase()}</span>
                    </td>
                    <td className="col-task">
                      <div className="unit-task">{u.task}</div>
                      {u.rationale && <div className="unit-rationale">{u.rationale}</div>}
                    </td>
                    <td className="col-target">
                      <strong>{u.target_candidate_id ?? "—"}</strong>
                      {u.target_kind && <div className="unit-sub">{u.target_kind.replace(/_/g, " ")}</div>}
                      {u.requested_target_candidate_id && u.requested_target_candidate_id !== u.target_candidate_id && (
                        <div className="unit-flag">Requested: {u.requested_target_candidate_id} (stripped by guardrail)</div>
                      )}
                      {u.guardrail_flags?.length ? (
                        <div className="unit-flag">Guardrail: {u.guardrail_flags.join(", ")}</div>
                      ) : null}
                    </td>
                    <td className="col-pri">
                      <div><strong>#{u.priority_rank ?? "-"}</strong></div>
                      <div className="unit-sub">ETA: {u.eta_minutes_estimate != null ? `${u.eta_minutes_estimate}m` : "TBD"}</div>
                    </td>
                    <td className="col-status">
                      <span className={`tag ${u.dispatch_status === "dispatched" ? "tag-green" : "tag-yellow"}`}>
                        {u.dispatch_status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="dispatch-detail-grid">
            <div className="dispatch-detail-col">
              {plan.phases?.length > 0 && (
                <div className="summary-card">
                  <div className="summary-card-label">OPERATIONAL PHASES</div>
                  <ol className="phase-list">
                    {plan.phases.map((ph) => (
                      <li key={ph.phase}>
                        <strong>Phase {ph.phase} — {ph.name}:</strong> {ph.actions.join("; ")}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {plan.safety_brief?.length > 0 && (
                <div className="summary-card">
                  <div className="summary-card-label">VERIFIED SAFETY BRIEF</div>
                  <ul className="plain-list">
                    {plan.safety_brief.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}

              {plan.communications_plan && (
                <div className="summary-card">
                  <div className="summary-card-label">COMMUNICATIONS &amp; GUARDRAIL AUDIT</div>
                  <p><strong>Comms Plan:</strong> {plan.communications_plan}</p>
                  {d.guardrail?.actions?.length > 0 && (
                    <ul className="plain-list" style={{ marginTop: 8 }}>
                      {d.guardrail.actions.map((a, i) => (
                        <li key={i}><strong>{a.unit_id}</strong> — {a.action}: {a.detail}</li>
                      ))}
                    </ul>
                  )}
                  <p style={{ marginTop: 8, fontSize: 12 }}>
                    <strong>Verified Basis:</strong> Corridors [{d.input_basis.verified_corridors.join(", ") || "none"}] · Landing Zones [{d.input_basis.verified_landing_zones.join(", ") || "none"}] · Excluded Rejected [{d.input_basis.excluded_rejected_candidate_ids.join(", ") || "none"}]
                  </p>
                </div>
              )}
            </div>

            <div className="dispatch-detail-col">
              <div className="summary-card">
                <div className="summary-card-label">TACTICAL BRIEFING CARD (muse-image-1.0)</div>
                {d.briefing_card?.status === "ok" && d.briefing_card.image_base64 ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    className="briefing-card"
                    src={`data:image/png;base64,${d.briefing_card.image_base64}`}
                    alt="muse-image-1.0 tactical briefing card generated from verified facts only"
                  />
                ) : d.briefing_card?.status === "ok" && d.briefing_card.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    className="briefing-card"
                    src={d.briefing_card.image_url}
                    alt="muse-image-1.0 tactical briefing card generated from verified facts only"
                  />
                ) : d.briefing_card ? (
                  <p style={{ margin: 0, fontSize: 12.5 }}>
                    Briefing card failed honestly ({d.briefing_card.error?.message ?? "unknown error"}). No card was fabricated; the unit protocol above still stands on verified data.
                  </p>
                ) : (
                  <p style={{ margin: 0, fontSize: 12.5 }}>No briefing card requested for this run.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
