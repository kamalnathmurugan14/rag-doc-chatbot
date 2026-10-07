"""Paragraph-aware chunker with overlap. Keeps page numbers and character offsets."""

import re
from dataclasses import dataclass

_PARA = re.compile(r"\S(?:.*?\S)?(?=[ \t]*\n\s*\n|\s*\Z)", re.S)


@dataclass
class Chunk:
    index: int
    page: int
    text: str
    char_start: int  # offsets are relative to the page text
    char_end: int


def _units(text: str, size: int) -> list[tuple[int, int]]:
    """Paragraph spans; paragraphs longer than `size` are cut at whitespace."""
    spans: list[tuple[int, int]] = []
    for m in _PARA.finditer(text):
        s, e = m.start(), m.end()
        while e - s > size:
            cut = text.rfind(" ", s + size // 2, s + size)
            cut = cut if cut > s else s + size
            spans.append((s, cut))
            s = cut
            while s < e and text[s].isspace():
                s += 1
        if s < e:
            spans.append((s, e))
    return spans


def chunk_pages(pages: list[tuple[int, str]], size: int = 1000, overlap: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page, text in pages:
        units = _units(text, size)
        i, lead = 0, None  # `lead`: char offset where overlap text from the previous chunk begins
        while i < len(units):
            start = units[i][0] if lead is None else lead
            j = i
            while j + 1 < len(units) and units[j + 1][1] - start <= size:
                j += 1
            end = units[j][1]
            chunks.append(Chunk(len(chunks), page, text[start:end], start, end))
            if j + 1 >= len(units):
                break
            # overlap: step back over whole units that fit in `overlap`, else back up a few words
            nxt = j + 1
            while nxt - 1 > i and end - units[nxt - 1][0] <= overlap:
                nxt -= 1
            lead = None
            if nxt == j + 1 and overlap > 0:
                cut = max(end - overlap, start + 1)
                sp = text.find(" ", cut, units[nxt][0])  # snap forward to a word boundary
                if sp != -1 and units[nxt][1] - (sp + 1) <= size:
                    lead = sp + 1
            i = nxt
    return chunks
