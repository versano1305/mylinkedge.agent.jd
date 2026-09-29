"""Normalize Neo4j ``evidence`` JSON on instance-to-skill edges."""

from __future__ import annotations

import json
from typing import Any

from jd_agent.graphs.resume_generate.models import EvidenceEntry

_CONF_MAP: dict[str, float] = {"high": 0.9, "medium": 0.6, "low": 0.3}


def parse_evidence(raw_json: str | list[Any] | dict[str, Any] | None) -> list[EvidenceEntry]:
    """Parse and normalize the ``evidence`` property from a Neo4j edge.

    Applies the P-3 fallback: maps textual confidence strings to floats.
    """
    if not raw_json:
        return []
    try:
        data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []
    result: list[EvidenceEntry] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        raw_conf = entry.get("confidence", 0.0)
        if isinstance(raw_conf, str):
            raw_conf = _CONF_MAP.get(raw_conf.lower(), 0.0)
        result.append(
            EvidenceEntry(
                evidenceText=str(entry.get("evidenceText") or ""),
                sourceKind=str(entry.get("sourceKind") or ""),
                confidence=float(raw_conf),
                relType=str(entry.get("relType") or ""),
                sourceDocumentId=entry.get("sourceDocumentId"),
            )
        )
    return result
