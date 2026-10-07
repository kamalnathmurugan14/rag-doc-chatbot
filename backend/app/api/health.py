from fastapi import APIRouter, Request

from app.config import APP_VERSION

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    c = request.app.state.container
    try:
        chunks, chroma = c.store.count(), True
    except Exception:  # noqa: BLE001
        chunks, chroma = 0, False
    return {
        "status": "ok",
        "version": APP_VERSION,
        "chroma": chroma,
        "ollama": await c.llm.ping(),
        "embedder": c.embedder.name,
        "indexed_chunks": chunks,
        "model": c.llm.default_model,
        "reranker": c.reranker is not None,
    }
