from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/eval")


class EvalIn(BaseModel):
    questions_path: str | None = None
    inline: list[dict] | None = None
    chunk_tokens: list[int] | None = Field(default=None, max_length=6)
    top_k: list[int] | None = Field(default=None, max_length=6)
    mmr: bool = True
    rerank: bool = False
    judge: bool = False


@router.post("/run", status_code=202)
def run(request: Request, body: EvalIn) -> dict:
    """Starts one run per (chunk_tokens x top_k) combination: a parameter sweep."""
    e = request.app.state.container.eval
    questions = e.load_questions(body.questions_path, body.inline)
    return {"run_ids": e.start(questions, body.chunk_tokens, body.top_k, body.mmr, body.rerank, body.judge)}


@router.get("/runs")
def runs(request: Request) -> dict:
    return {"runs": request.app.state.container.eval.list_runs()}


@router.get("/runs/{run_id}")
def get_run(request: Request, run_id: int) -> dict:
    return request.app.state.container.eval.get(run_id)
