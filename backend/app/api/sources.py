from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.chat import Options, Scope
from app.errors import AppError

router = APIRouter()


class RetrieveIn(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    scope: Scope = Field(default_factory=Scope)
    options: Options = Field(default_factory=Options)


@router.get("/sources/{chunk_id}")
def source(request: Request, chunk_id: str) -> dict:
    c = request.app.state.container
    if ":" not in chunk_id or not chunk_id.replace(":", "").isdigit():
        raise AppError("BAD_CHUNK_ID", "chunk_id looks like '12:3'", 422)
    h = c.store.get(chunk_id)
    if h is None:
        raise AppError("CHUNK_NOT_FOUND", "Unknown chunk", 404)
    nb = c.store.neighbors(chunk_id)
    return {
        "chunk_id": chunk_id,
        "text": h.text,
        "rel_path": h.meta["rel_path"],
        "page": h.meta["page"],
        "char_start": h.meta["char_start"],
        "char_end": h.meta["char_end"],
        "neighbors": [nb["prev"], nb["next"]],
    }


@router.post("/retrieve")
def retrieve(request: Request, body: RetrieveIn) -> dict:
    """Retrieval only (no LLM): inspect what the search returns and why."""
    c = request.app.state.container
    paths = c.chat.resolve_scope(body.scope.model_dump())
    opt = c.retriever.options(body.options.top_k, body.options.mmr, body.options.rerank)
    r = c.retriever.retrieve(body.query, paths, opt)
    return {
        "hits": [
            {
                "n": i,
                "chunk_id": h.chunk_id,
                "rel_path": h.meta["rel_path"],
                "page": h.meta["page"],
                "similarity": round(h.similarity, 4),
                "rerank": h.extra.get("rerank"),
                "text": h.text,
            }
            for i, h in enumerate(r.hits, 1)
        ],
        "debug": r.debug,
    }
