"""Extract numeric impact spans from resume source text (WU-05 / WU-11 allow-list)."""

from __future__ import annotations

import re

_METRIC_RE = re.compile(
    r"""
    \$\d[\d,]*(?:\.\d+)?(?:[kKmM])? |
    \d+(?:\.\d+)?\s?(?:%|x|ms|s|sec|secs|seconds?|hours?|hrs?|days?|weeks?|months?|years?) |
    \d+(?:\.\d+)?\s?[kKmM]\b |
    \d+(?:\.\d+)?\+
    """,
    re.VERBOSE | re.I,
)


def extract_metrics(text: str, *, extra: str | None = None) -> list[str]:
    """Return deduplicated metric strings found in ``text`` and optional ``extra``."""

    found: list[str] = []
    seen: set[str] = set()
    for chunk in (text, extra or ""):
        if not chunk:
            continue
        for m in _METRIC_RE.finditer(chunk):
            span = m.group(0).strip()
            key = span.lower()
            if key not in seen:
                seen.add(key)
                found.append(span)
    return found
