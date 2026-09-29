"""WU-02 — Load the candidate dossier from Neo4j.

Reads every resume-relevant subgraph for the owner in one Cypher round-trip,
normalizes dates and evidence, and writes a typed ``Dossier`` to state.

Input:  ``state["user_id"]``  — the Neo4j ``ownerId`` set by WU-01.
Output: ``state["dossier"]``  — ``Dossier.model_dump()``.

No ``Person.id`` is used. The traversal is rooted at
``Person {ownerId: $user_id}``; WU-01 guarantees at most one such node.
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.integrations.skills_graph.candidate_dossier import fetch_candidate_dossier


def load_dossier(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Hydrate ``dossier`` from the Neo4j data graph for this owner."""

    _ = config
    user_id = str(state.get("user_id") or "").strip()
    if not user_id:
        raise ValueError("user_id is required before load_dossier (set by WU-01)")

    dossier = fetch_candidate_dossier(user_id)
    return {"dossier": dossier.model_dump()}
