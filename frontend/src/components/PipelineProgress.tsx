import type { RunEvent } from "../api/types";

const STAGES = ["extractor", "generator", "validator", "delegator", "distributor"];
const LABELS: Record<string, string> = {
  extractor: "Extract requirements",
  generator: "Generate tests",
  validator: "Validate (harness)",
  delegator: "Delegate",
  distributor: "Distribute",
};

export function PipelineProgress({ nodes }: { nodes: Extract<RunEvent, { type: "node" }>[] }) {
  const done = new Set(nodes.map((n) => n.node));
  const validations = nodes.filter((n) => n.node === "validator");

  return (
    <section className="panel">
      <h3>Pipeline</h3>
      <ol className="pipeline">
        {STAGES.map((s) => (
          <li key={s} className={done.has(s) ? "done" : ""}>
            {LABELS[s]}
            {s === "delegator" && done.has(s) && !done.has("distributor") && (
              <span className="hint"> · paused for manager approval</span>
            )}
          </li>
        ))}
      </ol>
      {validations.map((v, i) => (
        <p key={i} className={v.failures?.length ? "warn-text" : "ok-text"}>
          Validation pass {i + 1}: {v.accepted} accepted
          {v.failures?.length ? `, ${v.failures.length} rejected (${v.failures.join(", ")}) → retrying` : ", all clean"}
        </p>
      ))}
    </section>
  );
}
