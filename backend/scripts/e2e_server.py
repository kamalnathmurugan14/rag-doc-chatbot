"""Throw-away backend for Playwright: temp docs, hashing embedder, scripted demo LLM (no Ollama needed). Served on :8000."""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import uvicorn  # noqa: E402

from app.config import Settings  # noqa: E402
from app.deps import Container  # noqa: E402
from app.llm.client import Token, Usage  # noqa: E402
from app.main import create_app  # noqa: E402


class DemoLLM:
    default_model = "demo-model"

    async def stream(self, messages, params):
        prompt = messages[-1]["content"]
        if "Standalone question" in prompt:
            reply = "how many annual leave days carry over"
        elif "grading an answer" in prompt:
            reply = '{"correctness": 2, "faithfulness": 2}'
        else:
            reply = "Employees receive 24 days of paid annual leave [1]."
        for w in reply.split(" "):
            yield Token(w + " ")
            await asyncio.sleep(0.02)
        yield Usage(40, len(reply.split()))

    async def models(self):
        return ["demo-model"]

    async def ping(self):
        return True


tmp = Path(tempfile.mkdtemp())
docs = tmp / "docs"
(docs / "hr").mkdir(parents=True)
(docs / "hr" / "leave_policy.txt").write_text(
    "Employees receive 24 days of paid annual leave each year. Unused vacation days carry over up to 5 days.",
    encoding="utf-8",
)
(docs / "it.txt").write_text(
    "Passwords must be rotated every 90 days. Use the company VPN when working remotely.", encoding="utf-8"
)
s = Settings(docs_root=docs, data_dir=tmp / "data", embedding_model="hashing", min_similarity=0.0, _env_file=None)
uvicorn.run(create_app(s, Container(s, llm=DemoLLM())), host="127.0.0.1", port=8000, log_level="warning")
