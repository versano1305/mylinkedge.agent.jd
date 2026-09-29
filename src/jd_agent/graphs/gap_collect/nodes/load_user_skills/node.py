"""Load the candidate's evidenced (held) skills from the data graph."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.gap_collect.state import GapCollectState
from jd_agent.integrations.skills_graph import fetch_user_skill_ids


def load_user_skills(
    state: GapCollectState, config: RunnableConfig
) -> dict[str, Any]:
    """Populate ``user_skill_ids`` (held) and ``evidence_skill_ids`` (seeds).

    v1 treats every held skill as evidence-backed (Confirmed-eligible). A later
    revision can split reachable-without-evidence from evidence-backed by adding
    an evidence-tier query, seeding ``evidence_skill_ids`` from that instead.
    """
    _ = config
    user_id = str(state.get("user_id") or "").strip()
    if not user_id:
        raise ValueError("user_id is required before load_user_skills")

    held = fetch_user_skill_ids(user_id)
    return {"user_skill_ids": held, "evidence_skill_ids": held}
