import { useCallback, useEffect, useState } from "react";
import { api, post, type IngestStatus } from "../api/client";

interface Props {
  paths?: string[];
  onFinished?: () => void;
  compact?: boolean;
}

export function IngestProgress({ paths, onFinished, compact }: Props) {
  const [st, setSt] = useState<IngestStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    try {
      setSt(await api<IngestStatus>("/ingest/status"));
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const running = st?.state === "running";
  useEffect(() => {
    if (!running) return;
    const id = setInterval(async () => {
      const s = await api<IngestStatus>("/ingest/status").catch(() => null);
      if (s) {
        setSt(s);
        if (s.state !== "running") onFinished?.();
      }
    }, 500);
    return () => clearInterval(id);
  }, [running, onFinished]);
  const start = async (force: boolean, only?: string[]) => {
    try {
      await post("/ingest", { force, paths: only });
      await refresh();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  return (
    <div className={compact ? "" : "card"}>
      <div className="row">
        <button className="primary" type="button" disabled={running} onClick={() => start(false)}>
          {running ? "Indexing…" : "Index"}
        </button>
        {!compact && (
          <button type="button" disabled={running} onClick={() => start(true)}>
            Force full re-index
          </button>
        )}
        {!compact && paths && (
          <button type="button" disabled={running || paths.length === 0} onClick={() => start(true, paths)}>
            Re-index selected ({paths.length})
          </button>
        )}
        <span className="muted">{st?.indexed_chunks ?? 0} chunks</span>
      </div>
      {running && st && (
        <p>
          <progress max={Math.max(st.total, 1)} value={st.done} aria-label="Indexing progress" />{" "}
          <span className="muted">
            {st.done}/{st.total} {st.current}
          </span>
        </p>
      )}
      {st?.state === "done" &&
        st.errors.length > 0 &&
        st.errors.map((e) => (
          <p key={e.rel_path} className="error">
            ⚠ {e.rel_path}: {e.error}
          </p>
        ))}
      {err && (
        <p className="error" role="alert">
          {err}
        </p>
      )}
    </div>
  );
}
