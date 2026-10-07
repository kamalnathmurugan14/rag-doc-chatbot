"""query -> embed -> Chroma (filtered) -> drop low similarity -> [MMR] -> [rerank] -> top_k, with per-stage debug info."""

import time
from dataclasses import dataclass, field

import numpy as np

from app.config import Settings
from app.rag.embedder import Embedder
from app.rag.mmr import mmr
from app.rag.reranker import Reranker
from app.rag.vector_store import Hit, VectorStore


@dataclass
class RetrievalOptions:
    top_k: int
    mmr: bool
    rerank: bool
    min_similarity: float
    fetch_k: int
    mmr_lambda: float


@dataclass
class Retrieval:
    hits: list[Hit]
    debug: dict = field(default_factory=dict)


class Retriever:
    def __init__(self, settings: Settings, embedder: Embedder, store: VectorStore, reranker: Reranker | None) -> None:
        self.s, self.embedder, self.store, self.reranker = settings, embedder, store, reranker

    def options(
        self, top_k: int | None = None, use_mmr: bool | None = None, rerank: bool | None = None
    ) -> RetrievalOptions:
        s = self.s
        return RetrievalOptions(
            top_k or s.top_k,
            s.use_mmr if use_mmr is None else use_mmr,
            s.use_reranker if rerank is None else rerank,
            s.min_similarity,
            max(s.fetch_k, top_k or s.top_k),
            s.mmr_lambda,
        )

    def retrieve(self, query: str, rel_paths: list[str] | None, opt: RetrievalOptions) -> Retrieval:
        timings: dict[str, float] = {}
        t = time.perf_counter()
        qv = self.embedder.encode([query])[0]
        timings["embed_ms"] = (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        fetched = self.store.query(qv, opt.fetch_k, rel_paths)
        timings["vector_search_ms"] = (time.perf_counter() - t) * 1000
        hits = [h for h in fetched if h.similarity >= opt.min_similarity]
        dropped = len(fetched) - len(hits)
        stages = ["similarity"]
        if opt.mmr and len(hits) > 1:
            t = time.perf_counter()
            mat = np.vstack([h.embedding for h in hits])
            order = mmr(qv, mat, min(len(hits), opt.fetch_k), opt.mmr_lambda)
            hits = [hits[i] for i in order]
            timings["mmr_ms"] = (time.perf_counter() - t) * 1000
            stages.append("mmr")
        rerank_status = "off"
        if opt.rerank:
            if self.reranker is None:
                rerank_status = "unavailable"
            elif hits:
                t = time.perf_counter()
                scores = self.reranker.score(query, [h.text for h in hits])
                for h, sc in zip(hits, scores, strict=True):
                    h.extra["rerank"] = sc
                hits = sorted(hits, key=lambda h: -h.extra["rerank"])
                timings["rerank_ms"] = (time.perf_counter() - t) * 1000
                rerank_status = "applied"
                stages.append("rerank")
        hits = hits[: opt.top_k]
        for rank, h in enumerate(hits, 1):
            h.extra["rank"] = rank
        debug = {
            "query": query,
            "fetched": len(fetched),
            "below_min_similarity": dropped,
            "stages": stages,
            "rerank": rerank_status,
            "embedder": self.embedder.name,
            "timings_ms": {k: round(v, 1) for k, v in timings.items()},
            "options": {"top_k": opt.top_k, "mmr": opt.mmr, "rerank": opt.rerank, "min_similarity": opt.min_similarity},
        }
        return Retrieval(hits, debug)
