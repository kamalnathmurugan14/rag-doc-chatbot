"""Map [n] markers in the model output back to retrieved chunks."""

import re

_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def map_citations(answer: str, sources: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (cited, also_consulted). Invalid numbers are dropped; each source appears once, in order of first mention."""
    by_n = {s["n"]: s for s in sources}
    order: list[int] = []
    for m in _CITE.finditer(answer):
        for part in m.group(1).split(","):
            n = int(part)
            if n in by_n and n not in order:
                order.append(n)
    cited = [by_n[n] for n in order]
    others = [s for s in sources if s["n"] not in order]
    return cited, others
