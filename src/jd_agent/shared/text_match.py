"""Token overlap helpers for evidence-to-sentence attachment."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-z0-9]+", re.I)


def normalize_for_match(text: str) -> str:
    """Lowercase, collapse whitespace, strip outer punctuation."""

    s = " ".join(text.split()).lower()
    return s.strip(".,;:!?\"'()[]")


def token_set(text: str) -> set[str]:
    return set(_WORD_RE.findall(normalize_for_match(text)))


def token_jaccard(a: str, b: str) -> float:
    """Jaccard similarity over word tokens."""

    ta, tb = token_set(a), token_set(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0
