"""Wires services together."""

import logging

from app.config import Settings
from app.db.session import init_db
from app.llm.client import LLM, OllamaClient
from app.rag.embedder import Embedder, build_embedder
from app.rag.reranker import Reranker, build_reranker
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore
from app.services.chat_service import ChatService
from app.services.eval_service import EvalService
from app.services.ingestion_service import IngestionService

log = logging.getLogger(__name__)


class Container:
    def __init__(
        self,
        settings: Settings,
        llm: LLM | None = None,
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        store: VectorStore | None = None,
    ) -> None:
        self.settings = settings
        settings.docs_root.mkdir(parents=True, exist_ok=True)
        init_db(settings.db_path)
        self.llm: LLM = llm or OllamaClient(settings)
        self.embedder = embedder or build_embedder(settings.embedding_model)
        self.reranker = (
            reranker
            if reranker is not None
            else (build_reranker(settings.rerank_model) if settings.use_reranker else None)
        )
        self.store = store or VectorStore.persistent(settings.chroma_dir)
        self.retriever = Retriever(settings, self.embedder, self.store, self.reranker)
        self.ingestion = IngestionService(settings, self.embedder, self.store)
        self.chat = ChatService(settings, self.llm, self.retriever)
        self.eval = EvalService(settings, self.llm, self.embedder, self.store, self.reranker)
