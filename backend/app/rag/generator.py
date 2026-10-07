"""Streams the answer from the LLM."""

from collections.abc import AsyncIterator

from app.llm.client import LLM, LLMEvent
from app.llm.options import GenParams


def generate(llm: LLM, messages: list[dict], params: GenParams) -> AsyncIterator[LLMEvent]:
    return llm.stream(messages, params)
