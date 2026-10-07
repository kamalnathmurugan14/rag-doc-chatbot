import { api, type Health } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { useOptions } from "../hooks/useOptions";

export function SettingsPage() {
  const health = useAsync(() => api<Health>("/health"), []);
  const [o, setO] = useOptions();
  const h = health.data;
  return (
    <>
      <h2>Settings</h2>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Backend</h3>
        {health.error && (
          <p className="error" role="alert">
            {health.error}
          </p>
        )}
        {h && (
          <ul className="plain">
            <li>
              API: <strong>{h.status}</strong> v{h.version}
            </li>
            <li>
              ChromaDB: {h.chroma ? "✔" : "✘"} · {h.indexed_chunks} chunks
            </li>
            <li>
              Ollama: {h.ollama ? "✔" : "✘ — run `ollama serve` and `ollama pull " + h.model + "`"} (model{" "}
              {h.model})
            </li>
            <li>
              Embedder: <code>{h.embedder}</code>
              {h.embedder === "hashing" &&
                " (offline lexical fallback — install sentence-transformers for semantic search)"}
            </li>
            <li>Reranker: {h.reranker ? "loaded" : "not loaded"}</li>
          </ul>
        )}
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Chat options</h3>
        <div className="row">
          <label>
            Top-k{" "}
            <input
              type="number"
              min={1}
              max={20}
              value={o.top_k}
              onChange={(e) => setO({ ...o, top_k: Number(e.target.value) })}
            />
          </label>
          <label>
            Temperature{" "}
            <input
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={o.temperature}
              onChange={(e) => setO({ ...o, temperature: Number(e.target.value) })}
            />
          </label>
          <label className="row">
            <input
              type="checkbox"
              checked={!!o.mmr}
              onChange={(e) => setO({ ...o, mmr: e.target.checked })}
            />{" "}
            MMR (diversify)
          </label>
          <label className="row">
            <input
              type="checkbox"
              checked={!!o.rerank}
              onChange={(e) => setO({ ...o, rerank: e.target.checked })}
            />{" "}
            Cross-encoder rerank
          </label>
        </div>
        <p className="muted">
          Saved in this browser. Toggle MMR/rerank, ask the same question, and compare the sources in the
          Debug view (A/B).
        </p>
      </div>
    </>
  );
}
