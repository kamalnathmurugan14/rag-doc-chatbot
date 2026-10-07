"""Rough token counting (no tokenizer dependency). Good enough to budget the context window."""

import math


def estimate_tokens(text: str) -> int:
    """~4 ASCII chars per token; non-Latin scripts (Tamil, ...) cost far more per character."""
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    other = len(text) - ascii_chars
    return math.ceil(ascii_chars / 4 + other * 0.75)
