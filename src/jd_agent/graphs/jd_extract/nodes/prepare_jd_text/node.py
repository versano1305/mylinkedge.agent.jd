"""LangGraph node: normalize input into plain-text ``jd_text``."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.jd_extract.nodes.prepare_jd_text.text import resolve_plain_text
from jd_agent.graphs.jd_extract.state import JdExtractState


def prepare_jd_text(state: JdExtractState) -> dict[str, Any]:
    """Normalize the input into plain-text ``jd_text``.

    Runs for every path (copy_paste or fetched URL content). When
    ``jd_text`` is already set (URL path after ``fetch_jd``), returns an
    empty patch. Otherwise copies ``jd.origin_jd`` (pasted text).
    """
    if str(state.get("jd_text") or "").strip():
        return {}

    plain = resolve_plain_text(dict(state)).strip()
    if not plain:
        raise ValueError("jd_text is empty after prepare_jd_text")
    return {"jd_text": plain}
