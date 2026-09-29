"""Owner-scoped node reads from the Neo4j data database.

Candidate data is keyed by ``ownerId`` (= Supabase ``user_id``), the same key
:mod:`user_skills` uses. Callers pass the node label so it can come from the
taxonomy snapshot rather than a hardcoded string.
"""

from __future__ import annotations

from mylinkedge_agent_tools.skills.settings import Neo4jSettings
from neo4j import Driver

from jd_agent.integrations.skills_graph.user_skills import _get_driver


def count_owner_nodes(
    user_id: str, label: str, *, driver: Driver | None = None
) -> int:
    """Return how many ``label`` nodes carry ``ownerId = user_id``."""
    uid = (user_id or "").strip()
    if not uid:
        return 0
    if not label or "`" in label:
        raise ValueError(f"Invalid node label: {label!r}")

    query = f"MATCH (n:`{label}` {{ownerId: $user_id}}) RETURN count(n) AS total"
    active_driver = driver or _get_driver()
    database = Neo4jSettings.from_env().resolved_data_database
    with active_driver.session(database=database) as session:
        record = session.run(query, user_id=uid).single()
    return int(record["total"]) if record else 0
