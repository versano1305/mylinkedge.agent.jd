"""Compiled gap collection graph.

Flow
----
1. ``load_session`` loads the ``user_resume_builder`` row + joined JD.
2. ``mark_analyzing`` sets status to ``gap-analysis_in_progress`` and publishes
   ``process.jd-gap-analysis/started``.
3. ``load_jd_targets`` normalizes the JD's extracted skills.
4. ``load_user_skills`` loads the candidate's held skills (supply seeds).
5. ``compute_gaps`` builds closures, zones, themes, and the review payload.
6. ``rank_queue`` attaches the expected-yield-ordered interview queue.
7. ``save_gaps`` writes ``gaps`` jsonb and advances to the gap-interview step.
8. ``mark_done`` publishes ``process.jd-gap-analysis/finish``.

Invoke input: ``{"session_id": "<user_resume_builder uuid>"}``.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from jd_agent.graphs.gap_collect.nodes import (
    compute_gaps_node,
    load_jd_targets,
    load_session,
    load_user_skills,
    mark_analyzing,
    mark_done,
    rank_queue_node,
    save_gaps,
)
from jd_agent.graphs.gap_collect.state import GapCollectState

builder = StateGraph(GapCollectState)

builder.add_node("load_session", load_session)
builder.add_node("mark_analyzing", mark_analyzing)
builder.add_node("load_jd_targets", load_jd_targets)
builder.add_node("load_user_skills", load_user_skills)
builder.add_node("compute_gaps", compute_gaps_node)
builder.add_node("rank_queue", rank_queue_node)
builder.add_node("save_gaps", save_gaps)
builder.add_node("mark_done", mark_done)

builder.add_edge(START, "load_session")
builder.add_edge("load_session", "mark_analyzing")
builder.add_edge("mark_analyzing", "load_jd_targets")
builder.add_edge("load_jd_targets", "load_user_skills")
builder.add_edge("load_user_skills", "compute_gaps")
builder.add_edge("compute_gaps", "rank_queue")
builder.add_edge("rank_queue", "save_gaps")
builder.add_edge("save_gaps", "mark_done")
builder.add_edge("mark_done", END)

graph = builder.compile(name="gap-collect")
