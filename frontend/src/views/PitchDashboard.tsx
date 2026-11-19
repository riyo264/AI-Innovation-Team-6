import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { RunDetail, Telemetry } from "../api/types";

/** The numbers for the judges: proof the AI is controlled, not just a wrapper. */
export function PitchDashboard({ run, refreshKey }: { run: RunDetail | null; refreshKey: number }) {
  const [scope, setScope] = useState<"run" | "all">("run");
  const [t, setT] = useState<Telemetry | null>(null);

  useEffect(() => {
    api.telemetry(scope === "run" ? run?.id : undefined).then(setT).catch(() => setT(null));
  }, [scope, run?.id, refreshKey]);

  if (!t) return <section className="panel muted">No telemetry yet.</section>;

  const assigned = t.test_cases_total - t.unassigned_total;
  const tiles: [string, string | number, string?][] = [
    ["Schema errors self-corrected", t.validation_failures_total, `${t.retry_loops_total} bounded retry loop(s)`],
    ["Test cases generated", t.test_cases_total, `from ${t.requirements_total} requirements`],
    ["Auto-delegated", assigned, `across ${t.developers_with_tasks} developers`],
    ["Manager overrides", t.overrides, `${Math.round(t.override_rate * 100)}% override rate`],
    ["Ambiguous reqs flagged", t.ambiguous_requirements],
    ["Tests passed / failed", `${t.executions_passed} / ${t.executions_failed}`],
    ["Avg LLM latency", `${Math.round(t.avg_llm_latency_ms)} ms`, `${t.llm_calls} calls`],
    ["Tokens", (t.prompt_tokens + t.completion_tokens).toLocaleString(), `${t.prompt_tokens.toLocaleString()} in / ${t.completion_tokens.toLocaleString()} out`],
  ];

  return (
    <div>
      <section className="panel toolbar">
        <h2>3 · Pitch dashboard</h2>
        <select value={scope} onChange={(e) => setScope(e.target.value as "run" | "all")}>
          <option value="run">This run</option>
          <option value="all">All runs</option>
        </select>
      </section>
      <p className="headline">
        The AI self-corrected <b>{t.validation_failures_total}</b> JSON/schema errors automatically, assigned{" "}
        <b>{assigned}</b> test cases across <b>{t.developers_with_tasks}</b> developers, and the manager only had to
        override <b>{t.overrides}</b>.
      </p>
      <div className="tiles">
        {tiles.map(([label, value, sub]) => (
          <div key={label} className="tile">
            <div className="tile-value">{value}</div>
            <div className="tile-label">{label}</div>
            {sub && <div className="muted small">{sub}</div>}
          </div>
        ))}
      </div>
      {scope === "run" && run && run.validation_failures.length > 0 && (
        <section className="panel">
          <h3>Harness log: what the Validator caught</h3>
          <table>
            <thead>
              <tr>
                <th>Attempt</th>
                <th>Type</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {run.validation_failures.map((f, i) => (
                <tr key={i}>
                  <td>{f.attempt}</td>
                  <td>{f.error_type}</td>
                  <td className="small">{f.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
