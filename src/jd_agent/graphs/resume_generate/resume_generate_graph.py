"""Compiled resume generation graph.

Flow
----
1. ``load_session`` loads the session + job description via the shared
   postgres lib, takes ``user_id`` as the Neo4j ``ownerId``, rejects owners
   with more than one ``Person`` node, and seeds template defaults.
2. ``mark_generating`` sets ``status = template_in_progress`` on the session
   and publishes ``process.resume-generate/started``.
3. ``load_dossier`` and ``load_jd_targets`` fan out, then join at
   ``score_demand``. ``load_jd_targets`` resolves JD skills to weighted
   seeds. ``build_atoms`` runs from the dossier branch.
4. ``license_and_value`` joins demand scoring and atoms.
5. ``allocate`` → ``build_briefs`` → ``generate_highlights`` →
   ``generate_summary`` → ``verify``.
6. ``route_after_verify`` re-sends failed instances to ``generate_highlights``
   or failed summary to ``generate_summary`` while repair rounds remain.
7. ``assemble_and_save`` builds resume + trace and persists via postgres;
   ``mark_done`` publishes ``process.resume-generate/finish``.

Invoke input: ``{"session_id": "<user_resume_builder uuid>"}``.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from jd_agent.graphs.resume_generate.nodes import (
    allocate,
    assemble_and_save,
    build_atoms,
    build_briefs,
    generate_highlights,
    generate_summary,
    license_and_value,
    load_dossier,
    load_jd_targets,
    load_session,
    mark_done,
    mark_generating,
    score_demand,
    verify,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.dispatch import (
    build_highlight_sends,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.node import (
    dispatch_highlights_after_briefs,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def route_after_verify(state: ResumeGenerateState) -> list | str:
    """Repair highlights and/or summary, or continue to assembly."""
    verification = state.get("verification")
    if not isinstance(verification, dict):
        return "assemble_and_save"
    if not verification.get("needs_repair"):
        return "assemble_and_save"

    if verification.get("failed_instances"):
        sends = build_highlight_sends(state, from_repair=True)
        if sends:
            return sends
    if verification.get("failed_summary"):
        return "generate_summary"
    return "assemble_and_save"


builder = StateGraph(ResumeGenerateState)

builder.add_node("load_session", load_session)
builder.add_node("mark_generating", mark_generating)
builder.add_node("load_dossier", load_dossier)
builder.add_node("load_jd_targets", load_jd_targets)
builder.add_node("score_demand", score_demand)
builder.add_node("build_atoms", build_atoms)
builder.add_node("license_and_value", license_and_value)
builder.add_node("allocate", allocate)
builder.add_node("build_briefs", build_briefs)
builder.add_node("generate_highlights", generate_highlights)
builder.add_node("generate_summary", generate_summary)
builder.add_node("verify", verify)
builder.add_node("assemble_and_save", assemble_and_save)
builder.add_node("mark_done", mark_done)

builder.add_edge(START, "load_session")
builder.add_edge("load_session", "mark_generating")
builder.add_edge("mark_generating", "load_dossier")
builder.add_edge("mark_generating", "load_jd_targets")
builder.add_edge("load_dossier", "score_demand")
builder.add_edge("load_jd_targets", "score_demand")
builder.add_edge("load_dossier", "build_atoms")
builder.add_edge("score_demand", "license_and_value")
builder.add_edge("build_atoms", "license_and_value")
builder.add_edge("license_and_value", "allocate")
builder.add_edge("allocate", "build_briefs")
builder.add_conditional_edges(
    "build_briefs",
    dispatch_highlights_after_briefs,
    ["generate_highlights", "generate_summary"],
)
builder.add_edge("generate_highlights", "generate_summary")
builder.add_edge("generate_summary", "verify")
builder.add_conditional_edges(
    "verify",
    route_after_verify,
    ["generate_highlights", "generate_summary", "assemble_and_save"],
)
builder.add_edge("assemble_and_save", "mark_done")
builder.add_edge("mark_done", END)

graph = builder.compile(name="resume-generate")
