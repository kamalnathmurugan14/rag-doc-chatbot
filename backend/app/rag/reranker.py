"""Optional cross-encoder reranker: reads (query, passage) TOGETHER, so it is slower but usually more precise than embeddings."""

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder  # heavy, lazy

        self.model = CrossEncoder(model_name)

    def score(self, query: str, passages: list[str]) -> list[float]:
        return [float(x) for x in self.model.predict([(query, p) for p in passages])]


def build_reranker(model_name: str) -> Reranker | None:
    try:
        return CrossEncoderReranker(model_name)
    except Exception as exc:  # noqa: BLE001 - not installed / no network
        log.warning("reranker_unavailable model=%s reason=%s", model_name, type(exc).__name__)
        return None
