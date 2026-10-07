"""One chat turn: rewrite -> retrieve -> prompt -> stream -> citations -> persist. Yields {"event","data"} dicts."""

import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from app.config import Settings
from app.db.session import connect
from app.errors import AppError
from app.llm.client import LLM, Token, Usage
from app.llm.options import GenParams
from app.llm.token_utils import estimate_tokens
from app.rag.citations import map_citations
from app.rag.generator import generate
from app.rag.prompt_builder import NOT_FOUND, build_prompt
from app.rag.query_rewriter import rewrite_query
from app.rag.retriever import Retriever

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def snippet(text: str, n: int = 220) -> str:
    t = " ".join(text.split())
    return t if len(t) <= n else t[:n] + "…"


class ChatService:
    def __init__(self, settings: Settings, llm: LLM, retriever: Retriever) -> None:
        self.s, self.llm, self.retriever = settings, llm, retriever

    # ---- sessions ---------------------------------------------------
    def create_session(self, title: str, scope: dict | None = None) -> int:
        with connect(self.s.db_path) as con:
            return int(
                con.execute(
                    "INSERT INTO chat_sessions(title, created_at, scope_json) VALUES(?,?,?)",
                    (title[:60] or "New chat", _now(), json.dumps(scope or {})),
                ).lastrowid
            )

    def history(self, session_id: int) -> list[dict]:
        with connect(self.s.db_path) as con:
            rows = con.execute(
                "SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, self.s.max_history_turns * 2),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def _save(self, session_id: int, role: str, content: str, citations=None, debug=None) -> int:
        with connect(self.s.db_path) as con:
            return int(
                con.execute(
                    "INSERT INTO messages(session_id, role, content, citations_json, debug_json, created_at) VALUES(?,?,?,?,?,?)",
                    (
                        session_id,
                        role,
                        content,
                        json.dumps(citations) if citations is not None else None,
                        json.dumps(debug) if debug is not None else None,
                        _now(),
                    ),
                ).lastrowid
            )

    def resolve_scope(self, scope: dict | None) -> list[str] | None:
        """files + folders -> explicit list of indexed rel_paths (None = everything)."""
        if not scope or not (scope.get("files") or scope.get("folders")):
            return None
        wanted = set(scope.get("files") or [])
        with connect(self.s.db_path) as con:
            rows = [r["rel_path"] for r in con.execute("SELECT rel_path FROM files WHERE status='indexed'")]
        for folder in scope.get("folders") or []:
            prefix = folder.strip("/") + "/"
            wanted.update(p for p in rows if p.startswith(prefix))
        return sorted(wanted & set(rows)) or [
            "__no_match__"
        ]  # an impossible path -> empty retrieval, never "everything"

    # ---- the turn ---------------------------------------------------
    async def ask(
        self, session_id: int | None, question: str, scope: dict | None, options: dict | None
    ) -> AsyncIterator[dict]:
        options = options or {}
        sid = session_id or self.create_session(question, scope)
        with connect(self.s.db_path) as con:
            if con.execute("SELECT 1 FROM chat_sessions WHERE id=?", (sid,)).fetchone() is None:
                raise AppError("SESSION_NOT_FOUND", "Chat session not found", 404)
        history = self.history(sid)
        paths = self.resolve_scope(scope)
        return self._events(sid, question, history, paths, options)

    async def _events(
        self, sid: int, question: str, history: list[dict], paths: list[str] | None, options: dict
    ) -> AsyncIterator[dict]:
        t0 = time.perf_counter()
        answer: list[str] = []
        tokens_in = tokens_out = 0
        saved = False
        params = GenParams(temperature=options.get("temperature"), max_tokens=self.s.max_answer_tokens)
        try:
            self._save(sid, "user", question)
            # 1) query rewriting (only with history)
            t = time.perf_counter()
            standalone = await rewrite_query(self.llm, question, history) if history else question
            rewrite_ms = (time.perf_counter() - t) * 1000
            yield {
                "event": "rewritten_query",
                "data": {"query": standalone, "rewritten": standalone != question, "original": question},
            }
            # 2) retrieval
            opt = self.retriever.options(options.get("top_k"), options.get("mmr"), options.get("rerank"))
            retrieval = self.retriever.retrieve(standalone, paths, opt)
            # 3) prompt (trimmed to the context window)
            messages, used, dropped = build_prompt(
                standalone, retrieval.hits, history, self.s.context_tokens, self.s.max_answer_tokens
            )
            sources = [
                {
                    "n": i,
                    "chunk_id": h.chunk_id,
                    "rel_path": h.meta["rel_path"],
                    "page": h.meta["page"],
                    "similarity": round(h.similarity, 4),
                    "rerank": round(h.extra["rerank"], 4) if "rerank" in h.extra else None,
                    "snippet": snippet(h.text),
                }
                for i, h in enumerate(used, 1)
            ]
            yield {"event": "sources", "data": {"sources": sources}}
            debug = {
                **retrieval.debug,
                "rewritten_query": standalone,
                "rewrite_ms": round(rewrite_ms, 1),
                "sources": sources,
                "dropped_for_budget": [h.chunk_id for h in dropped],
                "prompt": messages[-1]["content"],
                "history_turns": len(history) // 2,
            }
            # 4) generation (or the fixed "not found" answer when nothing relevant was retrieved)
            if not used:
                answer.append(NOT_FOUND)
                yield {"event": "token", "data": {"text": NOT_FOUND}}
            else:
                t = time.perf_counter()
                async for ev in generate(self.llm, messages, params):
                    if isinstance(ev, Token):
                        answer.append(ev.text)
                        yield {"event": "token", "data": {"text": ev.text}}
                    elif isinstance(ev, Usage):
                        tokens_in, tokens_out = ev.tokens_in, ev.tokens_out
                debug["timings_ms"]["generate_ms"] = round((time.perf_counter() - t) * 1000, 1)
            text = "".join(answer).strip()
            if not tokens_in:
                tokens_in = sum(estimate_tokens(m["content"]) for m in messages) if used else 0
                tokens_out = estimate_tokens(text)
            cited, others = ([], sources) if text.startswith(NOT_FOUND) else map_citations(text, sources)
            debug["timings_ms"]["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            debug["usage"] = {"tokens_in": tokens_in, "tokens_out": tokens_out}
            mid = self._save(sid, "assistant", text, {"cited": cited, "also_consulted": others}, debug)
            saved = True
            yield {
                "event": "done",
                "data": {
                    "session_id": sid,
                    "message_id": mid,
                    "citations": cited,
                    "also_consulted": others,
                    "usage": {"tokens_in": tokens_in, "tokens_out": tokens_out},
                    "debug": debug,
                },
            }
        except AppError as exc:
            yield {"event": "error", "data": {"code": exc.code, "message": exc.message}}
        finally:
            if not saved and answer:  # client stopped / disconnected mid-answer: keep what was produced
                self._save(
                    sid,
                    "assistant",
                    "".join(answer).strip() + " …(stopped)",
                    {"cited": [], "also_consulted": []},
                    {"stopped": True},
                )
