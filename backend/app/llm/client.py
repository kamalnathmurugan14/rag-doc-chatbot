"""LLM client abstraction. OllamaClient streams /api/chat; tests inject a fake with the same interface."""

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings
from app.errors import AppError
from app.llm.options import GenParams

log = logging.getLogger(__name__)


@dataclass
class Token:
    text: str


@dataclass
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0


LLMEvent = Token | Usage


class LLM(Protocol):
    default_model: str

    def stream(self, messages: list[dict], params: GenParams) -> AsyncIterator[LLMEvent]: ...
    async def models(self) -> list[str]: ...
    async def ping(self) -> bool: ...


async def complete(llm: LLM, messages: list[dict], params: GenParams) -> tuple[str, Usage]:
    """Collect a whole answer (used for map steps and JSON extraction)."""
    parts: list[str] = []
    usage = Usage()
    async for ev in llm.stream(messages, params):
        if isinstance(ev, Token):
            parts.append(ev.text)
        else:
            usage = ev
    return "".join(parts), usage


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.default_model = settings.ollama_model

    def _hint(self, model: str) -> str:
        return f"Make sure Ollama is running (`ollama serve`) and the model is installed: `ollama pull {model}`"

    async def stream(self, messages: list[dict], params: GenParams) -> AsyncIterator[LLMEvent]:
        model = params.model or self.default_model
        body = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": params.ollama_options(
                self.s.default_temperature, self.s.default_max_tokens, self.s.context_tokens
            ),
        }
        timeout = httpx.Timeout(self.s.llm_timeout_s, connect=5.0)
        try:
            async with (
                httpx.AsyncClient(timeout=timeout) as http,
                http.stream("POST", f"{self.s.ollama_base_url}/api/chat", json=body) as r,
            ):
                if r.status_code == 404:
                    raise AppError("MODEL_MISSING", f"Model '{model}' is not installed. {self._hint(model)}", 424)
                if r.status_code >= 400:
                    await r.aread()
                    raise AppError("LLM_ERROR", f"Ollama returned HTTP {r.status_code}", 502)
                async for (
                    line
                ) in r.aiter_lines():  # leaving this block (cancel/disconnect) closes the HTTP stream -> Ollama stops
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise AppError("LLM_ERROR", str(data["error"])[:300], 502)
                    piece = (data.get("message") or {}).get("content", "")
                    if piece:
                        yield Token(piece)
                    if data.get("done"):
                        yield Usage(data.get("prompt_eval_count", 0), data.get("eval_count", 0))
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise AppError(
                "LLM_UNAVAILABLE", f"Cannot reach Ollama at {self.s.ollama_base_url}. {self._hint(model)}", 503
            ) from exc
        except httpx.ReadTimeout as exc:
            raise AppError("LLM_TIMEOUT", "The model took too long to respond", 504) from exc

    async def models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as http:
                r = await http.get(f"{self.s.ollama_base_url}/api/tags")
                r.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                "LLM_UNAVAILABLE",
                f"Cannot reach Ollama at {self.s.ollama_base_url}. {self._hint(self.default_model)}",
                503,
            ) from exc
        return sorted(m["name"] for m in r.json().get("models", []))

    async def ping(self) -> bool:
        try:
            await self.models()
            return True
        except AppError:
            return False
