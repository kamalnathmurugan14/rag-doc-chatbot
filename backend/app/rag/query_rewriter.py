"""Turn a follow-up question into a standalone one (temperature 0). Skipped when there is no history."""

from app.llm.client import LLM, complete
from app.llm.options import GenParams
from app.rag.prompt_builder import render


async def rewrite_query(llm: LLM, question: str, history: list[dict], model: str | None = None) -> str:
    if not history:
        return question
    prompt = render("rewrite_followup", history=history, question=question)
    text, _ = await complete(
        llm, [{"role": "user", "content": prompt}], GenParams(model=model, temperature=0.0, max_tokens=120)
    )
    out = text.strip().strip('"').splitlines()[0].strip() if text.strip() else ""
    return out or question  # never fail the chat because of a bad rewrite
