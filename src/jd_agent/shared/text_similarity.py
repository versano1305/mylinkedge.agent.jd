"""Token overlap helpers for resume label matching."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+", re.I)


def tokenize(text: str) -> set[str]:
    return {m.group(0).casefold() for m in _TOKEN.finditer(str(text or ""))}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def best_label_match(
    candidates: list[str],
    target: str,
    *,
    tie_rank: list[str] | None = None,
) -> str:
    """Pick the candidate string most similar to ``target`` (token Jaccard).

    ``tie_rank`` lists candidate strings in priority order (e.g. recency).
    """

    target_tokens = tokenize(target)
    if not candidates:
        return ""
    if not target_tokens:
        return candidates[0]

    ranked = tie_rank or candidates
    rank_index = {c: i for i, c in enumerate(ranked)}

    def score(label: str) -> tuple[float, int]:
        sim = jaccard(tokenize(label), target_tokens)
        return (sim, -rank_index.get(label, len(ranked)))

    return max(candidates, key=score)
