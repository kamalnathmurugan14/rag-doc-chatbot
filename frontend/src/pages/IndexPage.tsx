import { useState } from "react";
import { api, type FileRow } from "../api/client";
import { IngestProgress } from "../components/IngestProgress";
import { useAsync } from "../hooks/useAsync";

export function IndexPage() {
  const files = useAsync(() => api<{ files: FileRow[] }>("/files"), []);
  const [sel, setSel] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const clear = async () => {
    if (!window.confirm("Delete the whole index? Your documents are not touched.")) return;
    try {
      await api("/index?confirm=true", { method: "DELETE" });
      setSel([]);
      files.reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  const toggle = (p: string) => setSel((s) => (s.includes(p) ? s.filter((x) => x !== p) : [...s, p]));
  return (
    <>
      <h2>Index</h2>
      <IngestProgress paths={sel} onFinished={files.reload} />
      <div className="card">
        <div className="row">
          <h3 style={{ margin: 0, flex: 1 }}>Files ({files.data?.files.length ?? 0})</h3>
          <button type="button" onClick={files.reload}>
            Refresh
          </button>
          <button type="button" onClick={clear}>
            Clear index…
          </button>
        </div>
        {(files.error || err) && (
          <p className="error" role="alert">
            {files.error ?? err}
          </p>
        )}
        {files.loading && <p className="muted">Loading…</p>}
        {files.data?.files.length === 0 && (
          <p className="empty">Nothing indexed yet. Put documents in DOCS_ROOT and press Index.</p>
        )}
        {!!files.data?.files.length && (
          <table>
            <thead>
              <tr>
                <th />
                <th>file</th>
                <th>status</th>
                <th className="num">chunks</th>
                <th>indexed</th>
              </tr>
            </thead>
            <tbody>
              {files.data.files.map((f) => (
                <tr key={f.rel_path}>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Select ${f.rel_path}`}
                      checked={sel.includes(f.rel_path)}
                      onChange={() => toggle(f.rel_path)}
                    />
                  </td>
                  <td>{f.rel_path}</td>
                  <td className={f.status === "error" ? "error" : ""} title={f.error ?? ""}>
                    {f.status}
                    {f.error ? ` – ${f.error}` : ""}
                  </td>
                  <td className="num">{f.n_chunks}</td>
                  <td className="muted">{f.indexed_at ? new Date(f.indexed_at).toLocaleString() : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
