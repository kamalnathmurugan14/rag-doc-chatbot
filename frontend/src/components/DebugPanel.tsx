import type { Message } from "../api/client";

export function DebugPanel({ m, onClose }: { m: Message; onClose: () => void }) {
  const d = m.debug;
  if (!d) return null;
  return (
    <aside className="side card" aria-label="Debug">
      <div className="row">
        <h3 style={{ margin: 0, flex: 1 }}>Retrieval debug</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <p>
        <strong>Query:</strong> {d.rewritten_query}
      </p>
      <p className="muted">
        {d.fetched} fetched · {d.below_min_similarity} below min similarity ({d.options.min_similarity}) ·
        stages: {d.stages.join(" → ")} · rerank: {d.rerank} · embedder: {d.embedder}
      </p>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>file</th>
            <th className="num">sim</th>
            <th className="num">rerank</th>
          </tr>
        </thead>
        <tbody>
          {d.sources.map((s) => (
            <tr key={s.chunk_id}>
              <td>{s.n}</td>
              <td title={s.snippet}>
                {s.rel_path} p.{s.page}
              </td>
              <td className="num">{s.similarity.toFixed(3)}</td>
              <td className="num">{s.rerank?.toFixed(2) ?? "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {d.dropped_for_budget.length > 0 && (
        <p className="warn">Dropped to fit the context window: {d.dropped_for_budget.join(", ")}</p>
      )}
      <h4>Timing (ms)</h4>
      <ul className="plain">
        {Object.entries(d.timings_ms).map(([k, v]) => (
          <li key={k}>
            {k}: {v}
          </li>
        ))}
      </ul>
      {d.usage && (
        <p>
          Tokens: {d.usage.tokens_in} in / {d.usage.tokens_out} out
        </p>
      )}
      <details>
        <summary>Final prompt</summary>
        <pre className="output">{d.prompt}</pre>
      </details>
    </aside>
  );
}
