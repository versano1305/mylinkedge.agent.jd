"""Conservative sentence splitting for experience summaries."""

from __future__ import annotations

import re

_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_TRAILING_ABBREV = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|Inc|Ltd|Corp|Co|vs|etc|e\.g|i\.e)\.$",
    re.I,
)


def split_sentences(text: str) -> list[str]:
    """Split narrative text into sentences without breaking common abbreviations."""

    raw = " ".join(text.split()).strip()
    if not raw:
        return []

    parts = _SENT_BOUNDARY.split(raw)
    merged: list[str] = []
    buf = ""
    for part in parts:
        chunk = f"{buf} {part}".strip() if buf else part.strip()
        if _TRAILING_ABBREV.search(chunk):
            buf = chunk
            continue
        merged.append(chunk)
        buf = ""
    if buf:
        if merged:
            merged[-1] = f"{merged[-1]} {buf}".strip()
        else:
            merged.append(buf.strip())
    return [s for s in merged if s]
