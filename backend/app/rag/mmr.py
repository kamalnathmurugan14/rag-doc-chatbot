"""Maximal Marginal Relevance: pick results that are relevant AND different from each other."""

import numpy as np


def mmr(query_vec: np.ndarray, doc_vecs: np.ndarray, k: int, lam: float = 0.6) -> list[int]:
    """Return indices of up to k docs. score = lam * sim(query, doc) - (1-lam) * max sim(doc, already_selected)."""
    n = len(doc_vecs)
    if n == 0:
        return []
    rel = doc_vecs @ query_vec
    selected: list[int] = []
    candidates = list(range(n))
    while candidates and len(selected) < k:
        if not selected:
            best = max(candidates, key=lambda i: rel[i])
        else:
            sel = doc_vecs[selected]
            best = max(candidates, key=lambda i: lam * rel[i] - (1 - lam) * float((sel @ doc_vecs[i]).max()))
        selected.append(best)
        candidates.remove(best)
    return selected
