"""Ingestion: scan -> extract -> clean -> chunk -> embed -> Chroma, incremental by SHA-256, as a background job."""

import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.core.chunker import chunk_pages
from app.core.cleaner import clean_text
from app.core.extractors import extract
from app.core.hashing import sha256_of
from app.core.paths import ext_of, is_inside, rel_posix, safe_resolve
from app.db.session import connect
from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore

log = logging.getLogger(__name__)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def chunk_file(path: Path, chunk_tokens: int, overlap_pct: int) -> list:
    """Extract + clean + chunk one file. Page numbers are kept on every chunk."""
    ex = extract(path)
    pages = [(n, clean_text(t)) for n, t in ex.pages]
    size = max(200, chunk_tokens * 4)  # ~4 chars per token
    return chunk_pages([(n, t) for n, t in pages if t], size=size, overlap=size * overlap_pct // 100)


def add_file_to_store(
    store: VectorStore,
    embedder: Embedder,
    path: Path,
    rel: str,
    file_id: int,
    sha: str,
    chunk_tokens: int,
    overlap_pct: int,
) -> int:
    chunks = chunk_file(path, chunk_tokens, overlap_pct)
    if not chunks:
        return 0
    name = rel.rsplit("/", 1)[-1]
    # the embedded text gets a short header (helps retrieval); the stored/displayed text stays clean
    vecs = embedder.encode([f"File: {name}, Page: {c.page}\n{c.text}" for c in chunks])
    store.add(
        ids=[f"{file_id}:{c.index}" for c in chunks],
        embeddings=vecs,
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "file_id": file_id,
                "rel_path": rel,
                "page": c.page,
                "chunk_index": c.index,
                "sha256": sha,
                "ext": ext_of(rel),
                "char_start": c.char_start,
                "char_end": c.char_end,
            }
            for c in chunks
        ],
    )
    return len(chunks)


class IngestionService:
    def __init__(self, settings: Settings, embedder: Embedder, store: VectorStore) -> None:
        self.s, self.embedder, self.store = settings, embedder, store
        self._lock = threading.Lock()
        self.job: dict = {"job_id": None, "state": "idle", "done": 0, "total": 0, "current": None, "errors": []}
        self.thread: threading.Thread | None = None

    @property
    def signature(self) -> str:
        return f"{self.embedder.name}:{self.embedder.dim}:{self.s.chunk_tokens}:{self.s.chunk_overlap_pct}"

    def start(self, force: bool = False, paths: list[str] | None = None) -> str | None:
        with self._lock:
            if self.job["state"] == "running":
                return None
            job_id = uuid.uuid4().hex[:10]
            self.job = {"job_id": job_id, "state": "running", "done": 0, "total": 0, "current": None, "errors": []}
        sel = [rel_posix(self.s.docs_root, safe_resolve(self.s.docs_root, p)) for p in paths] if paths else None
        self.thread = threading.Thread(target=self._run, args=(force, sel), daemon=True)
        self.thread.start()
        return job_id

    def run_blocking(self, force: bool = False, paths: list[str] | None = None) -> str:
        job_id = self.start(force, paths)
        assert job_id and self.thread
        self.thread.join()
        return job_id

    def status(self) -> dict:
        return dict(self.job)

    def clear(self) -> None:
        self.store.reset()
        with connect(self.s.db_path) as con:
            con.execute("DELETE FROM files")
            con.execute("DELETE FROM meta WHERE key='signature'")

    def _scan(self) -> list[Path]:
        root = self.s.docs_root.resolve()
        out = []
        for p in sorted(root.rglob("*")):
            parts = p.relative_to(root).parts
            if (
                p.is_file()
                and not any(x.startswith(".") for x in parts)
                and ext_of(p.name) in self.s.extensions
                and is_inside(root, p)
            ):
                out.append(p)
        return out

    def _run(self, force: bool, only: list[str] | None) -> None:
        try:
            root = self.s.docs_root.resolve()
            with connect(self.s.db_path) as con:
                prev = con.execute("SELECT value FROM meta WHERE key='signature'").fetchone()
                if prev is None or prev["value"] != self.signature:
                    # embedder or chunking changed: old vectors are incompatible -> start over
                    if prev is not None:
                        self.store.reset()
                        con.execute("DELETE FROM files")
                    con.execute("INSERT OR REPLACE INTO meta VALUES('signature', ?)", (self.signature,))
                    force = True
                known = {r["rel_path"]: dict(r) for r in con.execute("SELECT * FROM files")}
            files = [p for p in self._scan() if only is None or rel_posix(root, p) in only]
            self.job["total"] = len(files)
            seen = set()
            for path in files:
                rel = rel_posix(root, path)
                seen.add(rel)
                self.job["current"] = rel
                try:
                    self._index_one(path, rel, known.get(rel), force or (only is not None))
                except Exception as exc:  # noqa: BLE001 - one bad file must not stop the job
                    log.warning("ingest_error file=%s err=%s", rel, type(exc).__name__)
                    self.job["errors"].append({"rel_path": rel, "error": f"{type(exc).__name__}: {exc}"[:300]})
                    self._record(rel, path, known.get(rel), "error", 0, str(exc)[:300])
                self.job["done"] += 1
            if only is None:  # full run: forget files that disappeared
                with connect(self.s.db_path) as con:
                    for rel, row in known.items():
                        if rel not in seen:
                            self.store.delete_file(row["id"])
                            con.execute("DELETE FROM files WHERE id=?", (row["id"],))
        except Exception as exc:  # noqa: BLE001
            log.exception("ingest_job_failed")
            self.job["errors"].append({"rel_path": "*", "error": str(exc)[:300]})
        finally:
            self.job["state"] = "done"
            self.job["current"] = None

    def _record(
        self, rel: str, path: Path, old: dict | None, status: str, n: int, error: str | None, sha: str = ""
    ) -> int:
        """Upsert the files row (by rel_path) and return its id. Safe to call twice for the same file."""
        st = path.stat()
        with connect(self.s.db_path) as con:
            con.execute(
                "INSERT INTO files(rel_path,sha256,mtime,n_chunks,indexed_at,status,error) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(rel_path) DO UPDATE SET sha256=excluded.sha256, mtime=excluded.mtime, n_chunks=excluded.n_chunks, "
                "indexed_at=excluded.indexed_at, status=excluded.status, error=excluded.error",
                (rel, sha, st.st_mtime, n, now(), status, error),
            )
            return int(con.execute("SELECT id FROM files WHERE rel_path=?", (rel,)).fetchone()["id"])

    def _index_one(self, path: Path, rel: str, old: dict | None, force: bool) -> None:
        sha = sha256_of(path)
        if old and old["sha256"] == sha and old["status"] in ("indexed", "no_text") and not force:
            return  # unchanged -> skip
        if old:
            self.store.delete_file(old["id"])  # changed: remove the old vectors first
        file_id = self._record(rel, path, old, "pending", 0, None, sha)
        n = add_file_to_store(
            self.store, self.embedder, path, rel, file_id, sha, self.s.chunk_tokens, self.s.chunk_overlap_pct
        )
        self._record(rel, path, None, "indexed" if n else "no_text", n, None if n else "no extractable text", sha)
