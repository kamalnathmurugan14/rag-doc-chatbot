"""ChromaDB wrapper. We compute embeddings ourselves (collection has no embedding function) and use cosine distance."""

from dataclasses import dataclass, field
from pathlib import Path

import chromadb
import numpy as np

COLLECTION = "docs"


@dataclass
class Hit:
    chunk_id: str
    text: str
    meta: dict
    similarity: float
    embedding: np.ndarray | None = None
    extra: dict = field(default_factory=dict)  # rerank score, mmr rank, ...


class VectorStore:
    def __init__(self, client: chromadb.ClientAPI, name: str = COLLECTION) -> None:
        self.client, self.name = client, name
        self.col = self._open()

    @classmethod
    def persistent(cls, path: Path) -> "VectorStore":
        path.mkdir(parents=True, exist_ok=True)
        return cls(chromadb.PersistentClient(path=str(path)))

    @classmethod
    def ephemeral(cls) -> "VectorStore":
        """In-memory store used by the evaluation sweeps (a unique name avoids sharing state between instances)."""
        import uuid

        # EphemeralClient instances share one in-memory system, so isolate each store with its own collection name
        return cls(
            chromadb.EphemeralClient(settings=chromadb.Settings(anonymized_telemetry=False)),
            f"eval_{uuid.uuid4().hex[:10]}",
        )

    def _open(self):
        return self.client.get_or_create_collection(
            self.name, metadata={"hnsw:space": "cosine"}, embedding_function=None
        )

    def reset(self) -> None:
        """Drop everything (also needed when the embedding dimension changes)."""
        self.client.delete_collection(self.name)
        self.col = self._open()

    def count(self) -> int:
        return self.col.count()

    def add(self, ids: list[str], embeddings: np.ndarray, documents: list[str], metadatas: list[dict]) -> None:
        for i in range(0, len(ids), 256):  # keep batches small
            self.col.add(
                ids=ids[i : i + 256],
                embeddings=embeddings[i : i + 256].tolist(),
                documents=documents[i : i + 256],
                metadatas=metadatas[i : i + 256],
            )

    def delete_file(self, file_id: int) -> None:
        self.col.delete(where={"file_id": file_id})

    def query(self, embedding: np.ndarray, n: int, rel_paths: list[str] | None = None) -> list[Hit]:
        total = self.col.count()
        if total == 0 or (rel_paths is not None and not rel_paths):
            return []
        where = {"rel_path": {"$in": rel_paths}} if rel_paths is not None else None
        r = self.col.query(
            query_embeddings=[embedding.tolist()],
            n_results=min(n, total),
            where=where,
            include=["documents", "metadatas", "distances", "embeddings"],
        )
        hits = []
        for i, cid in enumerate(r["ids"][0]):
            hits.append(
                Hit(
                    cid,
                    r["documents"][0][i],
                    r["metadatas"][0][i],
                    1.0 - float(r["distances"][0][i]),
                    np.asarray(r["embeddings"][0][i], dtype=np.float32),
                )
            )
        return hits

    def get(self, chunk_id: str) -> Hit | None:
        r = self.col.get(ids=[chunk_id], include=["documents", "metadatas"])
        if not r["ids"]:
            return None
        return Hit(r["ids"][0], r["documents"][0], r["metadatas"][0], 0.0)

    def neighbors(self, chunk_id: str) -> dict:
        file_id, _, idx = chunk_id.partition(":")
        out: dict = {"prev": None, "next": None}
        for key, j in (("prev", int(idx) - 1), ("next", int(idx) + 1)):
            if j < 0:
                continue
            h = self.get(f"{file_id}:{j}")
            if h:
                out[key] = {"chunk_id": h.chunk_id, "text": h.text, "page": h.meta["page"]}
        return out
