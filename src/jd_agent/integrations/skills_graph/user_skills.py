"""Candidate held-skill reads from the Neo4j data database.

Mirrors the interview agent's helper: returns the global Skill ids evidenced for
a candidate ``ownerId``. Reuses the skills-graph :class:`Neo4jSettings` so the
gap collector and the skill-matching tool share one connection contract.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from mylinkedge_agent_tools.skills.settings import Neo4jSettings
from neo4j import Driver, GraphDatabase

# Any user-owned instance (Person / Experience / Project …) linked to a Skill.
USER_SKILL_IDS = """
MATCH (u {ownerId: $user_id})-[r]-(s:Skill)
WHERE s.id IS NOT NULL
RETURN DISTINCT s.id AS skill_id
ORDER BY skill_id
"""


@lru_cache(maxsize=1)
def _get_driver() -> Driver:
    settings = Neo4jSettings.from_env()
    return GraphDatabase.driver(
        settings.uri, auth=(settings.user, settings.password)
    )


def fetch_user_skill_ids(
    user_id: str, *, driver: Driver | None = None
) -> list[str]:
    """Return global Skill ids evidenced for a candidate ``ownerId``.

    A ``driver`` may be injected for tests; production builds one from env.
    """
    uid = (user_id or "").strip()
    if not uid:
        return []

    active_driver = driver or _get_driver()
    database = Neo4jSettings.from_env().resolved_data_database
    with active_driver.session(database=database) as session:
        rows: list[dict[str, Any]] = [dict(record) for record in session.run(
            USER_SKILL_IDS, user_id=uid
        )]
    return [
        str(row["skill_id"]).strip()
        for row in rows
        if row.get("skill_id") and str(row["skill_id"]).strip()
    ]
