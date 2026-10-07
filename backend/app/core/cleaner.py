"""Light text cleaning before chunking (keeps meaning, removes extraction noise)."""

import re

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")  # "infor-\nmation" -> "information" (common in PDFs)
_SPACES = re.compile(r"[ \t ]+")
_BLANKS = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    text = _CTRL.sub(" ", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = "\n".join(_SPACES.sub(" ", ln).strip() for ln in text.split("\n"))
    return _BLANKS.sub("\n\n", text).strip()
