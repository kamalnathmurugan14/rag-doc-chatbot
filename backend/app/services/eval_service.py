"""Evaluation harness: retrieval hit-rate@k + MRR, plus optional LLM-as-judge answer/faithfulness scores and keyword checks."""

import asyncio
import json
import logging
import threading
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

from app.config import Settings
from app.core.paths import ext_of, is_inside, rel_posix
from app.db.session import connect
from app.errors import AppError
from app.llm.client import LLM, Token, complete
from app.llm.options import GenParams
from app.rag.embedder import Embedder
from app.rag.prompt_builder import build_prompt, render
from app.rag.reranker import Reranker
from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore
from app.services.ingestion_service import add_file_to_store

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_items(lines: list[str]) -> list[dict]:
    items = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AppError("BAD_EVAL_FILE", f"Line {i} is not valid JSON", 422) from exc
        if not isinstance(obj, dict) or not obj.get("question"):
            raise AppError("BAD_EVAL_FILE", f"Line {i} needs a 'question'", 422)
        items.append(
            {
                "question": obj["question"],
                "expected_answer": obj.get("expected_answer", ""),
                "expected_files": obj.get("expected_files", []),
                "expected_keywords": obj.get("expected_keywords", []),
            }
        )
    if not items:
        raise AppError("BAD_EVAL_FILE", "The evaluation set is empty", 422)
    return items


def retrieval_metrics(retrieved: list[str], expected: list[str]) -> tuple[bool, float]:
    """hit@k: any expected file among the retrieved ones. RR: 1/rank of the first expected file (0 if none)."""
    for rank, rel in enumerate(retrieved, 1):
        if rel in expected:
            return True, 1.0 / rank
    return False, 0.0


def keyword_score(answer: str, keywords: list[str]) -> float | None:
    if not keywords:
        return None
    low = answer.lower()
    return sum(k.lower() in low for k in keywords) / len(keywords)


class EvalService:
    def __init__(
        self, settings: Settings, llm: LLM, embedder: Embedder, main_store: VectorStore, reranker: Reranker | None
    ) -> None:
        self.s, self.llm, self.embedder, self.main_store, self.reranker = settings, llm, embedder, main_store, reranker
        self.threads: list[threading.Thread] = []

    def load_questions(self, questions_path: str | None, inline: list[dict] | None) -> list[dict]:
        if inline:
            return parse_items([json.dumps(x) for x in inline])
        if not questions_path:
            raise AppError("MISSING_INPUT", "Provide questions_path or inline questions", 422)
        p = Path(questions_path)
        allowed = [self.s.docs_root.resolve(), (Path(__file__).resolve().parents[2] / "eval").resolve()]
        rp = (p if p.is_absolute() else self.s.docs_root / p).resolve()
        if not any(rp == a or a in rp.parents for a in allowed):
            raise AppError("PATH_FORBIDDEN", "Question files must live in DOCS_ROOT or backend/eval", 400)
        if not rp.is_file():
            raise AppError("NOT_FOUND", "Question file not found", 404)
        return parse_items(rp.read_text(encoding="utf-8").splitlines())

    def start(
        self,
        questions: list[dict],
        chunk_tokens: list[int] | None,
        top_k: list[int] | None,
        use_mmr: bool,
        rerank: bool,
        judge: bool,
    ) -> list[int]:
        combos = list(product(chunk_tokens or [self.s.chunk_tokens], top_k or [self.s.top_k]))
        run_ids = []
        with connect(self.s.db_path) as con:
            for ct, k in combos:
                params = {
                    "chunk_tokens": ct,
                    "top_k": k,
                    "mmr": use_mmr,
                    "rerank": rerank,
                    "judge": judge,
                    "n_questions": len(questions),
                }
                run_ids.append(
                    int(
                        con.execute(
                            "INSERT INTO eval_runs(params_json, created_at) VALUES(?,?)", (json.dumps(params), _now())
                        ).lastrowid
                    )
                )
        t = threading.Thread(
            target=self._run_all,
            args=(questions, list(zip(run_ids, combos, strict=True)), use_mmr, rerank, judge),
            daemon=True,
        )
        self.threads.append(t)
        t.start()
        return run_ids

    def _store_for(self, chunk_tokens: int) -> VectorStore:
        if chunk_tokens == self.s.chunk_tokens:
            return self.main_store
        store = VectorStore.ephemeral()  # a throw-away index with a different chunk size
        root = self.s.docs_root.resolve()
        for i, p in enumerate(sorted(root.rglob("*")), 1):
            if (
                p.is_file()
                and ext_of(p.name) in self.s.extensions
                and is_inside(root, p)
                and not any(x.startswith(".") for x in p.relative_to(root).parts)
            ):
                try:
                    add_file_to_store(
                        store, self.embedder, p, rel_posix(root, p), i, "", chunk_tokens, self.s.chunk_overlap_pct
                    )
                except Exception:  # noqa: BLE001
                    log.warning("eval_index_skip file=%s", p.name)
        return store

    def _run_all(self, questions, runs, use_mmr, rerank, judge) -> None:
        for run_id, (ct, k) in runs:
            try:
                self._run_one(run_id, questions, ct, k, use_mmr, rerank, judge)
            except Exception as exc:  # noqa: BLE001
                log.exception("eval_failed")
                with connect(self.s.db_path) as con:
                    con.execute(
                        "UPDATE eval_runs SET status='failed', details_json=? WHERE id=?",
                        (json.dumps({"error": str(exc)[:300]}), run_id),
                    )

    def _run_one(
        self, run_id: int, questions: list[dict], ct: int, k: int, use_mmr: bool, rerank: bool, judge: bool
    ) -> None:
        store = self._store_for(ct)
        retriever = Retriever(self.s, self.embedder, store, self.reranker)
        opt = retriever.options(k, use_mmr, rerank)
        details, hits, rrs, correct, faithful, kw = [], [], [], [], [], []
        for q in questions:
            r = retriever.retrieve(q["question"], None, opt)
            rels = list(dict.fromkeys(h.meta["rel_path"] for h in r.hits))
            hit, rr = retrieval_metrics(rels, q["expected_files"]) if q["expected_files"] else (None, None)
            row = {
                "question": q["question"],
                "retrieved_files": rels,
                "hit": hit,
                "rr": rr,
                "answer": None,
                "correctness": None,
                "faithfulness": None,
                "keyword_score": None,
            }
            if hit is not None:
                hits.append(hit)
                rrs.append(rr)
            if judge:
                ans, judged = asyncio.run(self._answer_and_judge(q, r.hits))
                row.update(answer=ans, **judged)
                row["keyword_score"] = keyword_score(ans, q["expected_keywords"])
                for key, bucket in (("correctness", correct), ("faithfulness", faithful), ("keyword_score", kw)):
                    if row[key] is not None:
                        bucket.append(row[key])
            details.append(row)
        mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None  # noqa: E731
        with connect(self.s.db_path) as con:
            con.execute(
                "UPDATE eval_runs SET hit_rate=?, mrr=?, avg_faithfulness=?, avg_answer_score=?, details_json=?, status='done' WHERE id=?",
                (
                    mean([1.0 if h else 0.0 for h in hits]),
                    mean(rrs),
                    mean(faithful),
                    mean(correct),
                    json.dumps({"questions": details, "keyword_score": mean(kw)}),
                    run_id,
                ),
            )

    async def _answer_and_judge(self, q: dict, hits) -> tuple[str, dict]:
        messages, used, _ = build_prompt(q["question"], hits, [], self.s.context_tokens, self.s.max_answer_tokens)
        parts = []
        async for ev in self.llm.stream(messages, GenParams(temperature=0.0, max_tokens=self.s.max_answer_tokens)):
            if isinstance(ev, Token):
                parts.append(ev.text)
        answer = "".join(parts).strip()
        context = "\n".join(f"[{i}] {h.text}" for i, h in enumerate(used, 1)) or "(nothing retrieved)"
        prompt = render(
            "judge",
            question=q["question"],
            expected=q["expected_answer"] or "(not provided)",
            context=context[:6000],
            answer=answer,
        )
        raw, _ = await complete(
            self.llm, [{"role": "user", "content": prompt}], GenParams(temperature=0.0, max_tokens=60)
        )
        try:
            obj = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
            c, f = max(0, min(2, int(obj["correctness"]))), max(0, min(2, int(obj["faithfulness"])))
            return answer, {"correctness": c / 2, "faithfulness": f / 2}
        except (ValueError, KeyError, TypeError):
            return answer, {
                "correctness": None,
                "faithfulness": None,
            }  # unparsable judge output is excluded, not counted as 0

    # ---- reads ----
    def get(self, run_id: int) -> dict:
        with connect(self.s.db_path) as con:
            r = con.execute("SELECT * FROM eval_runs WHERE id=?", (run_id,)).fetchone()
        if r is None:
            raise AppError("NOT_FOUND", "Evaluation run not found", 404)
        return self._row(r, True)

    def list_runs(self) -> list[dict]:
        with connect(self.s.db_path) as con:
            return [self._row(r, False) for r in con.execute("SELECT * FROM eval_runs ORDER BY id DESC LIMIT 100")]

    @staticmethod
    def _row(r, full: bool) -> dict:
        d = {
            "id": r["id"],
            "status": r["status"],
            "params": json.loads(r["params_json"]),
            "hit_rate": r["hit_rate"],
            "mrr": r["mrr"],
            "avg_faithfulness": r["avg_faithfulness"],
            "avg_answer_score": r["avg_answer_score"],
            "created_at": r["created_at"],
        }
        if full:
            d["details"] = json.loads(r["details_json"]) if r["details_json"] else None
        return d
