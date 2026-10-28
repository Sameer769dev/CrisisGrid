"use client";
// Dispatch Action Console - muse-wonder-1.0 units (verified targets only),
// deterministic guardrail holds, phases, safety brief, muse-image-1.0 briefing card,
// and 1-click Incident Action Plan (IAP) export (Markdown, JSON, PNG, Print).
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

function slugify(text: string): string {
  return (text || "crisisgrid-dispatch")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "dispatch";
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function DispatchConsole(p: Props) {
  const d = p.dispatch;
  const plan = d?.dispatch;
  const armed = !!plan && (plan.summary_counts?.units_dispatched ?? 0) > 0;
  const cleanOperationName = plan?.operation_name
    ? plan.operation_name.replace(/\s*[-–—]?\s*\bday\s*\d+\b/gi, "").trim() || "Verified Emergency Dispatch"
    : "";

  function handleExportMarkdown() {
    if (!d || !plan) return;
    const lines: string[] = [
      `# CRISISGRID — VERIFIED INCIDENT ACTION PLAN (IAP)`,
      ``,
      `- **Operation Name:** ${cleanOperationName}`,
      `- **Generated At:** ${new Date().toISOString()}`,
      `- **Models:** \`${d.models.dispatch}\` (reasoning effort: \`${d.reasoning.effort}\`) + \`${d.models.briefing_image}\``,
      `- **Confidence:** ${Math.round((plan.confidence ?? 0) * 100)}%`,
      `- **Units Summary:** ${plan.summary_counts.units_total} Total (${plan.summary_counts.units_dispatched} Dispatched, ${plan.summary_counts.units_held} Held by Guardrail)`,
      `- **Verified Corridors:** ${d.input_basis.verified_corridors.join(", ") || "none"}`,
      `- **Verified Landing Zones:** ${d.input_basis.verified_landing_zones.join(", ") || "none"}`,
      `- **Excluded Rejected Candidates:** ${d.input_basis.excluded_rejected_candidate_ids.join(", ") || "none"}`,
      ``,
      `## 1. Commander Summary`,
      plan.command_summary,
      ``,
      `## 2. Verified Situation Assessment`,
      plan.situation_assessment,
      ``,
      `## 3. Multi-Unit Dispatch Protocol`,
      `| Unit | Type | Staging | Verified Target | Pri | ETA | Status | Task & Rationale |`,
      `| :--- | :--- | :--- | :--- | :-: | :-: | :---: | :--- |`,
      ...plan.units.map((u) => {
        const target = u.target_candidate_id ? `${u.target_candidate_id} (${u.target_kind})` : "—";
        const eta = u.eta_minutes_estimate != null ? `${u.eta_minutes_estimate}m` : "TBD";
        const taskCell = `${u.task}${u.rationale ? ` — *${u.rationale}*` : ""}`.replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
        return `| **${u.unit_id}** | ${u.unit_type} | ${u.staging || "—"} | ${target} | #${u.priority_rank ?? "-"} | ${eta} | **${u.dispatch_status.toUpperCase()}** | ${taskCell} |`;
      }),
      ``,
    ];
    if (plan.phases?.length) {
      lines.push(`## 4. Operational Phases`);
      for (const ph of plan.phases) {
        lines.push(`${ph.phase}. **Phase ${ph.phase} — ${ph.name}:** ${ph.actions.join("; ")}`);
      }
      lines.push(``);
    }
    if (plan.safety_brief?.length) {
      lines.push(`## 5. Verified Safety Brief`);
      for (const s of plan.safety_brief) lines.push(`- ${s}`);
      lines.push(``);
    }
    if (plan.communications_plan) {
      lines.push(`## 6. Communications Plan`, plan.communications_plan, ``);
    }
    lines.push(
      `## 7. Deterministic Guardrail Audit`,
      `- **Engine:** \`${d.guardrail.engine}\` (${d.guardrail.model_calls} model calls)`,
      ...(d.guardrail.actions.length
        ? d.guardrail.actions.map((a) => `- **${a.unit_id}** (\`${a.action}\`): ${a.detail}`)
        : [`- All units targeted mathematically verified candidates; 0 guardrail holds triggered.`]),
      ``
    );
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    triggerDownload(blob, `crisisgrid-iap-${slugify(cleanOperationName)}.md`);
  }

  function handleExportJson() {
    if (!d) return;
    const blob = new Blob([JSON.stringify(d, null, 2)], { type: "application/json;charset=utf-8" });
    triggerDownload(blob, `crisisgrid-dispatch-${slugify(cleanOperationName)}.json`);
  }

  function handleDownloadCard() {
    if (!d?.briefing_card || d.briefing_card.status !== "ok") return;
    if (d.briefing_card.image_base64) {
      const byteString = atob(d.briefing_card.image_base64);
      const ab = new ArrayBuffer(byteString.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteString.length; i++) ia[i] = byteString.charCodeAt(i);
      triggerDownload(new Blob([ab], { type: "image/png" }), `crisisgrid-briefing-${slugify(cleanOperationName)}.png`);
    } else if (d.briefing_card.image_url) {
      window.open(d.briefing_card.image_url, "_blank", "noopener,noreferrer");
    }
  }

  return (
    <section className="panel dispatch-panel" aria-label="Dispatch action console">
      <div className="panel-head">
        <span>DISPATCH ACTION CONSOLE — muse-wonder-1.0</span>
        <span className={`tag ${armed ? "tag-green" : "tag-red"}`}>{armed ? "ARMED - VERIFIED" : "NOT ARMED"}</span>
      </div>

      <div className="dispatch-actions-bar">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
          <button type="button" className="btn btn-dispatch" disabled={!p.canDispatch || p.running} onClick={p.onDispatch}>
            {p.running ? "WONDER REASONING (HIGH EFFORT)..." : "STEP 4 - DISPATCH (muse-wonder-1.0)"}
          </button>
          <label className="check-row">
            <input type="checkbox" checked={p.includeCard} onChange={(e) => p.onIncludeCardChange(e.target.checked)} />
            Generate muse-image-1.0 tactical briefing card
          </label>
        </div>

        {d && plan && (
          <div className="export-bar" role="group" aria-label="Export Incident Action Plan">
            <button type="button" className="btn btn-small" onClick={handleExportMarkdown} title="Download human-readable Markdown Incident Action Plan">
              EXPORT IAP (.MD)
            </button>
            <button type="button" className="btn btn-small" onClick={handleExportJson} title="Download machine-readable verified JSON dispatch protocol">
              EXPORT JSON (.JSON)
            </button>
            {d.briefing_card?.status === "ok" && (
              <button type="button" className="btn btn-small" onClick={handleDownloadCard} title="Download muse-image-1.0 Tactical Briefing Card PNG">
                SAVE BRIEFING (.PNG)
              </button>
            )}
            <button type="button" className="btn btn-small" onClick={() => window.print()} title="Print or save PDF of Tactical Incident Action Plan">
              PRINT / PDF
            </button>
          </div>
        )}
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
