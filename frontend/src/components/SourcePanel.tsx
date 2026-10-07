import { api, type Source, type SourceDetail } from "../api/client";
import { useAsync } from "../hooks/useAsync";

/** Full chunk text with its neighbours; the cited chunk is highlighted. */
export function SourcePanel({ source, onClose }: { source: Source; onClose: () => void }) {
  const d = useAsync(
    () => api<SourceDetail>(`/sources/${encodeURIComponent(source.chunk_id)}`),
    [source.chunk_id],
  );
  return (
    <aside className="side card" aria-label="Source">
      <div className="row">
        <h3 style={{ margin: 0, flex: 1 }}>Source [{source.n}]</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="muted">
        {source.rel_path} · page {source.page} · similarity {source.similarity.toFixed(2)}
      </p>
      <div className="row">
        <button type="button" onClick={() => navigator.clipboard?.writeText(source.rel_path)}>
          Copy file path
        </button>
      </div>
      {d.loading && <p className="muted">Loading…</p>}
      {d.error && (
        <p className="error" role="alert">
          {d.error}
        </p>
      )}
      {d.data && (
        <>
          {d.data.neighbors[0] && (
            <p className="neighbor">
              <span className="muted">… previous chunk</span>
              <br />
              {d.data.neighbors[0].text}
            </p>
          )}
          <p className="current">
            <mark>{d.data.text}</mark>
          </p>
          {d.data.neighbors[1] && (
            <p className="neighbor">
              <span className="muted">next chunk …</span>
              <br />
              {d.data.neighbors[1].text}
            </p>
          )}
        </>
      )}
    </aside>
  );
}
