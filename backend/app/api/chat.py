from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.sse import sse

router = APIRouter()


class Scope(BaseModel):
    files: list[str] = []
    folders: list[str] = []


class Options(BaseModel):
    top_k: int | None = Field(default=None, ge=1, le=20)
    mmr: bool | None = None
    rerank: bool | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)


class ChatIn(BaseModel):
    session_id: int | None = None
    question: str = Field(min_length=1, max_length=4000)
    scope: Scope = Field(default_factory=Scope)
    options: Options = Field(default_factory=Options)


@router.post("/chat")
async def chat(request: Request, body: ChatIn):
    """SSE: rewritten_query, sources, token*, done {citations, usage, debug} | error. Disconnecting cancels generation."""
    events = await request.app.state.container.chat.ask(
        body.session_id, body.question, body.scope.model_dump(), body.options.model_dump()
    )
    return sse(events)
