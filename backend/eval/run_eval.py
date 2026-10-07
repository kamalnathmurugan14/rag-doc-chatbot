"""CLI sweep: python eval/run_eval.py eval/questions.sample.jsonl --chunk-tokens 300 600 --top-k 3 5 [--judge]

Prints a comparison table (hit-rate@k, MRR, judge scores). Uses your real .env (Ollama, embedder, DOCS_ROOT).
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402
from app.deps import Container  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("questions")
ap.add_argument("--chunk-tokens", type=int, nargs="*")
ap.add_argument("--top-k", type=int, nargs="*")
ap.add_argument("--mmr", action="store_true")
ap.add_argument("--rerank", action="store_true")
ap.add_argument("--judge", action="store_true")
args = ap.parse_args()

c = Container(get_settings())
c.ingestion.run_blocking()
items = c.eval.load_questions(args.questions, None)
ids = c.eval.start(items, args.chunk_tokens, args.top_k, args.mmr, args.rerank, args.judge)
for t in c.eval.threads:
    t.join()
print(f"{'chunk_tokens':>12} {'top_k':>6} {'hit@k':>7} {'MRR':>6} {'answer':>7} {'faithful':>9}")
f = lambda v: "   –  " if v is None else f"{v:6.2f}"  # noqa: E731
for i in ids:
    r = c.eval.get(i)
    p = r["params"]
    print(
        f"{p['chunk_tokens']:>12} {p['top_k']:>6} {f(r['hit_rate'])} {f(r['mrr'])} {f(r['avg_answer_score'])}  {f(r['avg_faithfulness'])}"
    )
time.sleep(0)
