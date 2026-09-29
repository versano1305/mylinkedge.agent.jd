"""Hydrate the resume-builder session, its job description, and the owner id.

Candidate data in Neo4j is keyed by ``ownerId`` (= ``session.user_id``). The
resume is built for exactly one ``Person`` per owner, so more than one
``Person`` node under the owner is an error. Zero is allowed here; later
nodes produce an empty dossier.
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from mylinkedge_agent_tools.postgres import get_postgres_db

from jd_agent.graphs.resume_generate.constants import DEFAULT_TEMPLATE
from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.graphs.resume_generate.taxonomy_types import node_type
from jd_agent.integrations.skills_graph import count_owner_nodes


def load_session(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Load the session + JD and verify the owner has at most one ``Person``."""

    _ = config
    session_id = str(state.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("session_id is required")

    loaded = get_postgres_db().user_resume_builders.get_with_job_description(session_id)
    if loaded is None:
        raise ValueError(f"No user_resume_builder row for id={session_id}")

    jd = loaded.job_description
    if jd.extraction_status != "done":
        raise ValueError(
            f"job_description {jd.id} is not extracted "
            f"(extraction_status={jd.extraction_status!r}); run jd_extract first"
        )

    user_id = loaded.session.user_id.strip()
    if not user_id:
        raise ValueError(f"user_resume_builder {session_id} has no user_id")

    person_count = count_owner_nodes(user_id, node_type("Person"))
    if person_count > 1:
        raise ValueError(
            f"ownerId={user_id} has {person_count} Person nodes; "
            "resume generation requires exactly one"
        )

    return {
        "session": loaded.session,
        "jd": jd,
        "user_id": user_id,
        "template": dict(DEFAULT_TEMPLATE),
        "generate_status": "generating",
    }
