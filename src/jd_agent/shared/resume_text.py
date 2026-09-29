"""Word and style helpers for resume generation and verification."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"\S+")
_FIRST_PERSON_RE = re.compile(r"\b(I|me|my|mine|we|our|ours)\b", re.I)


def word_count(text: str) -> int:
    """Count non-whitespace tokens."""

    return len(_WORD_RE.findall(text.strip()))


def leading_verb(text: str) -> str:
    """First word of ``text``, lowercased, or empty."""

    stripped = text.strip()
    if not stripped:
        return ""
    return stripped.split()[0].lower()


def contains_first_person(text: str) -> bool:
    return bool(_FIRST_PERSON_RE.search(text))
