"""Batch Skill property reads from the Neo4j data database.

Callers name the properties they need. The Cypher ``RETURN`` projects only
those names, and only names on a fixed allowlist are interpolated.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mylinkedge_agent_tools.skills.settings import Neo4jSettings
from neo4j import Driver

from jd_agent.integrations.skills_graph.user_skills import _get_driver

ALLOWED_SKILL_FIELDS: frozenset[str] = frozenset({"id", "name", "skillType"})


def fetch_skills_by_ids(
    skill_ids: Sequence[str],
    fields: Sequence[str],
    *,
    driver: Driver | None = None,
) -> dict[str, dict[str, str]]:
    """Return Skill rows keyed by id, each containing only ``fields``.

    ``id`` must be one of ``fields`` because results are keyed by it.
    An empty id list returns ``{}`` and does not open a session.
    A ``driver`` may be injected for tests; production builds one from env.
    """
    requested = _validated_fields(fields)
    ids = _clean_ids(skill_ids)
    if not ids:
        return {}

    active_driver = driver or _get_driver()
    database = Neo4jSettings.from_env().resolved_data_database
    query = _skills_by_ids_query(requested)
    with active_driver.session(database=database) as session:
        rows: list[dict[str, Any]] = [dict(record) for record in session.run(query, skill_ids=ids)]

    found: dict[str, dict[str, str]] = {}
    for row in rows:
        skill_id = str(row.get("id") or "").strip()
        if not skill_id:
            continue
        found[skill_id] = {field: str(row.get(field) or "").strip() for field in requested}
    return found


def _validated_fields(fields: Sequence[str]) -> tuple[str, ...]:
    if not fields:
        raise ValueError("fields must include at least one skill property")
    ordered: list[str] = []
    for field in fields:
        name = str(field).strip()
        if name not in ALLOWED_SKILL_FIELDS:
            raise ValueError(f"unsupported skill field: {field!r}")
        if name not in ordered:
            ordered.append(name)
    if "id" not in ordered:
        raise ValueError("fields must include 'id'")
    return tuple(ordered)


def _skills_by_ids_query(fields: Sequence[str]) -> str:
    parts: list[str] = []
    for field in fields:
        if field == "id":
            parts.append("s.id AS id")
        else:
            parts.append(f"coalesce(s.{field}, '') AS {field}")
    projection = ",\n       ".join(parts)
    return f"MATCH (s:Skill)\nWHERE s.id IN $skill_ids\nRETURN {projection}"


def _clean_ids(skill_ids: Sequence[str]) -> list[str]:
    seen: list[str] = []
    for raw in skill_ids:
        skill_id = str(raw or "").strip()
        if skill_id and skill_id not in seen:
            seen.append(skill_id)
    return seen
