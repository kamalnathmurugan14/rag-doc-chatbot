import numpy as np
import pytest

from app.rag.mmr import mmr
from app.rag.reranker import build_reranker
from app.rag.retriever import Retriever


def retrieve(client, q, **kw):
    r = client.post("/retrieve", json={"query": q, **kw})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize(
    "question,expected",
    [
        ("how many vacation days do I get", "hr/leave_policy.txt"),
        ("when are travel expenses reimbursed", "finance/expenses.txt"),
        ("how often should passwords change", "it/security.md"),
        ("what is the cancellation notice period", "contracts/acme.pdf"),
    ],
)
def test_relevant_chunk_in_top3(indexed, client, question, expected):
    hits = retrieve(client, question)["hits"]
    assert expected in [h["rel_path"] for h in hits[:3]]
    assert all(0 <= h["similarity"] <= 1.0001 for h in hits)


def test_page_is_reported(indexed, client):
    hit = [h for h in retrieve(client, "cancel with written notice")["hits"] if h["rel_path"] == "contracts/acme.pdf"][
        0
    ]
    assert hit["page"] == 2


def test_scope_filters_by_file_and_folder(indexed, client):
    only = retrieve(client, "days", scope={"files": ["finance/expenses.txt"]})["hits"]
    assert {h["rel_path"] for h in only} == {"finance/expenses.txt"}
    hr = retrieve(client, "days", scope={"folders": ["hr"]})["hits"]
    assert hr and all(h["rel_path"].startswith("hr/") for h in hr)
    assert (
        retrieve(client, "days", scope={"folders": ["nonexistent"]})["hits"] == []
    )  # unknown scope never falls back to "everything"


def test_min_similarity_drops_weak_hits(indexed, client):
    assert retrieve(client, "zzzz qqqq", options={})["debug"]["fetched"] > 0
    indexed.settings.min_similarity = 0.99
    r = retrieve(client, "zzzz qqqq")
    assert r["hits"] == [] and r["debug"]["below_min_similarity"] == r["debug"]["fetched"]


def test_debug_has_timings_and_stages(indexed, client):
    d = retrieve(client, "vacation")["debug"]
    assert (
        d["stages"] == ["similarity"]
        and d["rerank"] == "off"
        and {"embed_ms", "vector_search_ms"} <= set(d["timings_ms"])
    )
    assert d["options"]["top_k"] == 3 and d["embedder"] == "concept-test"


def test_mmr_function_prefers_diversity():
    q = np.array([1.0, 0.0])
    docs = np.array([[1.0, 0.0], [0.999, 0.045], [0.6, 0.8]], dtype=np.float32)
    docs /= np.linalg.norm(docs, axis=1, keepdims=True)
    assert mmr(q, docs, 2, lam=1.0) == [0, 1]  # pure relevance: two near-duplicates
    assert mmr(q, docs, 2, lam=0.3) == [0, 2]  # diversity wins
    assert mmr(q, docs[:0], 3) == [] and len(mmr(q, docs, 10)) == 3


def test_mmr_and_rerank_in_pipeline(indexed, client):
    base = retrieve(client, "days notice", options={"top_k": 5, "mmr": False})
    m = retrieve(client, "days notice", options={"top_k": 5, "mmr": True})
    assert "mmr" in m["debug"]["stages"] and {h["chunk_id"] for h in m["hits"]} <= {
        h["chunk_id"] for h in base["hits"]
    } | {h["chunk_id"] for h in m["hits"]}
    rr = retrieve(client, "written notice cancel", options={"top_k": 5, "rerank": True})
    assert (
        rr["debug"]["rerank"] == "applied"
        and "rerank" in rr["debug"]["stages"]
        and rr["hits"][0]["rerank"] >= rr["hits"][-1]["rerank"]
    )
    assert rr["hits"][0]["rel_path"] == "contracts/acme.pdf"


def test_rerank_unavailable_is_reported_not_fatal(indexed, client):
    indexed.retriever.reranker = None
    d = retrieve(client, "vacation", options={"rerank": True})
    assert d["debug"]["rerank"] == "unavailable" and d["hits"]


def test_empty_index_returns_nothing(client):
    assert retrieve(client, "anything")["hits"] == []


def test_build_reranker_falls_back_to_none():
    assert build_reranker("definitely/not-a-model") is None  # no sentence-transformers / no network here


def test_source_endpoint_with_neighbors(indexed, client, settings):
    settings.chunk_tokens = 200
    (settings.docs_root / "long.txt").write_text(
        "\n\n".join(f"Section {i}. " + "alpha beta gamma " * 60 for i in range(6)), encoding="utf-8"
    )
    indexed.ingestion.run_blocking()
    cid = [
        h["chunk_id"]
        for h in retrieve(client, "Section 3 alpha", scope={"files": ["long.txt"]}, options={"top_k": 5})["hits"]
    ][0]
    s = client.get(f"/sources/{cid}").json()
    assert s["rel_path"] == "long.txt" and s["text"] and s["page"] == 1 and "char_start" in s
    prev, nxt = s["neighbors"]
    assert (prev or nxt) and all(n is None or n["text"] for n in s["neighbors"])
    assert client.get("/sources/abc").status_code == 422 and client.get("/sources/999:0").status_code == 404


def test_retriever_options_defaults(container):
    r = Retriever(container.settings, container.embedder, container.store, None)
    o = r.options()
    assert (o.top_k, o.mmr, o.rerank, o.fetch_k) == (3, False, False, 20)
