"""Plain-text resolution helpers for ``prepare_jd_text``."""

from __future__ import annotations

from typing import Any


def resolve_plain_text(state: dict[str, Any]) -> str:
    """Return plain-text JD from state.

    Priority:
    1. ``jd_text`` — already resolved by ``fetch_jd`` (URL path).
    2. ``jd.origin_jd`` — pasted text for ``copy_paste`` origins.
    """
    existing = str(state.get("jd_text") or "").strip()
    if existing:
        return existing

    jd = state.get("jd")
    if jd is not None:
        origin_jd = getattr(jd, "origin_jd", None)
        if origin_jd is None and isinstance(jd, dict):
            origin_jd = jd.get("origin_jd")
        return str(origin_jd or "").strip()

    return ""
