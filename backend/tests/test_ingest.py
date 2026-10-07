import time

import pytest

from app.core.chunker import chunk_pages
from app.core.cleaner import clean_text
from app.db.session import connect
from tests.conftest import make_pdf


def rows(c):
    with connect(c.settings.db_path) as con:
        return {r["rel_path"]: dict(r) for r in con.execute("SELECT * FROM files")}


def test_cleaner():
    assert clean_text("infor-\nmation   is\x00  here\r\n\r\n\r\n\r\nnext") == "information is here\n\nnext"
    assert clean_text("   ") == ""


def test_chunker_keeps_pages_and_overlap_pct():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(10))
    ch = chunk_pages([(1, text), (2, text)], size=600, overlap=72)
    assert {c.page for c in ch} == {1, 2} and all(len(c.text) <= 600 for c in ch)


def test_full_index_and_status(indexed, client):
    r = rows(indexed)
    assert len(r) == 7 and all(v["status"] == "indexed" and v["n_chunks"] >= 1 for v in r.values())
    st = client.get("/ingest/status").json()
    assert (
        st["state"] == "done"
        and st["done"] == 7 == st["total"]
        and st["indexed_chunks"] == indexed.store.count() == sum(v["n_chunks"] for v in r.values())
    )
    files = client.get("/files").json()["files"]
    assert files[0]["rel_path"] == "contracts/acme.pdf" and files[0]["n_chunks"] >= 1


def test_embedded_text_has_header_stored_text_is_clean(indexed, embedder):
    embedded = [t for batch in embedder.calls for t in batch]
    assert any(t.startswith("File: leave_policy.txt, Page: 1\n") for t in embedded)
    h = indexed.store.get(f"{rows(indexed)['hr/leave_policy.txt']['id']}:0")
    assert h.text.startswith("Employees receive") and "File:" not in h.text
    assert (
        h.meta["rel_path"] == "hr/leave_policy.txt"
        and h.meta["page"] == 1
        and h.meta["ext"] == "txt"
        and len(h.meta["sha256"]) == 64
    )


def test_pdf_pages_are_kept(indexed):
    fid = rows(indexed)["contracts/acme.pdf"]["id"]
    pages = {
        indexed.store.get(f"{fid}:{i}").meta["page"] for i in range(rows(indexed)["contracts/acme.pdf"]["n_chunks"])
    }
    assert pages == {1, 2}


def test_unchanged_files_are_skipped(indexed, embedder):
    n = len(embedder.calls)
    indexed.ingestion.run_blocking()
    assert len(embedder.calls) == n  # nothing re-embedded


def test_modified_file_replaces_old_vectors(indexed, docs, embedder):
    before = indexed.store.count()
    (docs / "hr" / "leave_policy.txt").write_text("Remote work is allowed two days per week.", encoding="utf-8")
    indexed.ingestion.run_blocking()
    fid = rows(indexed)["hr/leave_policy.txt"]["id"]
    assert indexed.store.get(f"{fid}:0").text.startswith("Remote work")
    got = indexed.store.col.get(where={"file_id": fid})
    assert len(got["ids"]) == 1
    assert indexed.store.count() <= before
    assert all("24 days" not in d for d in indexed.store.col.get()["documents"])  # old text is gone


def test_removed_file_deletes_vectors(indexed, docs):
    fid = rows(indexed)["it/security.md"]["id"]
    (docs / "it" / "security.md").unlink()
    indexed.ingestion.run_blocking()
    assert "it/security.md" not in rows(indexed) and indexed.store.col.get(where={"file_id": fid})["ids"] == []


def test_new_file_added(indexed, docs):
    (docs / "new.txt").write_text("A brand new document about quarterly budgets.", encoding="utf-8")
    indexed.ingestion.run_blocking()
    assert rows(indexed)["new.txt"]["status"] == "indexed" and len(rows(indexed)) == 8


def test_bad_and_empty_files_do_not_stop_the_job(container, docs):
    make_pdf(docs / "blank.pdf", [""])
    (docs / "broken.pdf").write_bytes(b"not a pdf")
    container.ingestion.run_blocking()
    r = rows(container)
    assert (
        r["blank.pdf"]["status"] == "no_text"
        and r["broken.pdf"]["status"] == "error"
        and r["hr/leave_policy.txt"]["status"] == "indexed"
    )
    assert [e["rel_path"] for e in container.ingestion.status()["errors"]] == ["broken.pdf"]


def test_partial_reindex_of_selected_paths(indexed, embedder, docs):
    n = len(embedder.calls)
    indexed.ingestion.run_blocking(paths=["hr/leave_policy.txt"])
    assert (
        len(embedder.calls) == n + 1 and indexed.ingestion.status()["total"] == 1
    )  # only that file, even though unchanged


def test_force_and_signature_change_rebuild(indexed, embedder):
    n = len(embedder.calls)
    indexed.ingestion.run_blocking(force=True)
    assert len(embedder.calls) > n
    indexed.settings.chunk_tokens = 300  # chunk size is part of the index signature
    n = len(embedder.calls)
    indexed.ingestion.run_blocking()
    assert len(embedder.calls) > n and indexed.store.count() > 0


def test_ingest_api_lifecycle_and_clear(client):
    assert client.get("/ingest/status").json()["state"] == "idle"
    assert client.post("/ingest").status_code == 202
    for _ in range(100):
        if client.get("/ingest/status").json()["state"] == "done":
            break
        time.sleep(0.05)
    assert client.get("/ingest/status").json()["indexed_chunks"] > 0
    assert client.delete("/index").json()["error"]["code"] == "CONFIRM_REQUIRED"
    assert client.delete("/index", params={"confirm": True}).json() == {"cleared": True}
    assert client.get("/ingest/status").json()["indexed_chunks"] == 0 and client.get("/files").json()["files"] == []


def test_ingest_rejects_paths_outside_root(client):
    assert client.post("/ingest", json={"paths": ["../../etc/passwd"]}).status_code == 400


@pytest.mark.parametrize("n_files", [20])
def test_indexing_20_files_is_accurate(container, docs, n_files):
    for i in range(n_files):
        (docs / f"bulk_{i:02d}.txt").write_text(
            f"Bulk document number {i}. " + "Some filler sentence about topic. " * 20, encoding="utf-8"
        )
    container.ingestion.run_blocking()
    st = container.ingestion.status()
    assert st["total"] == st["done"] == 7 + n_files and rows(container)["bulk_07.txt"]["n_chunks"] >= 1
    assert container.store.count() == sum(v["n_chunks"] for v in rows(container).values())


def test_symlink_pointing_outside_docs_root_is_ignored_not_fatal(container, docs, tmp_path):
    secret = tmp_path / "outside_secret.txt"
    secret.write_text("TOP SECRET outside the docs folder", encoding="utf-8")
    (docs / "sneaky.txt").symlink_to(secret)
    container.ingestion.run_blocking()
    st = container.ingestion.status()
    assert st["total"] == 7 and st["done"] == 7 and st["errors"] == []  # the job finished normally
    assert "sneaky.txt" not in rows(container)
    assert not any("TOP SECRET" in d for d in container.store.col.get()["documents"])
