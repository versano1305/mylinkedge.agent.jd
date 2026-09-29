"""State schema for the resume generation graph.

``session_id`` is required: a ``user_resume_builder`` row already exists.
``load_session`` hydrates ``session``, ``jd`` and ``user_id``. Every Neo4j
read is scoped by ``ownerId = user_id``.

``generated`` uses a dict-merge reducer so parallel ``Send`` branches can
each write one instance's highlights.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from mylinkedge_agent_tools.postgres import JobDescription, UserResumeBuilder

ResumeGenerateStatus = Literal["generating", "done", "failed"]


def _merge_dicts(
    left: dict[str, Any] | None, right: dict[str, Any] | None
) -> dict[str, Any]:
    """Shallow-merge dict updates from parallel branches."""

    merged = dict(left or {})
    if right:
        merged.update(right)
    return merged


class ResumeGenerateState(TypedDict, total=False):
    """Shared state that flows through resume generation nodes."""

    # Input
    session_id: str

    # WU-01
    session: UserResumeBuilder
    jd: JobDescription
    user_id: str  # Neo4j ownerId
    template: dict[str, Any]

    # WU-02 / WU-03
    dossier: dict[str, Any]
    jd_targets: list[dict[str, Any]]  # resolved non-domain JD skills
    jd_domains: list[dict[str, Any]]  # resolved Domain skills, kept out of demand
    jd_context: dict[str, Any]  # title, company, requirements, unresolved names

    # WU-04
    demand: dict[str, Any]

    # WU-05 / WU-06 / WU-07
    atoms: list[dict[str, Any]]
    allocation: dict[str, Any]

    # WU-08 / WU-09 / WU-10
    briefs: dict[str, Any]
    # WU-09 Send worker payload (one instance per parallel branch)
    brief: dict[str, Any]
    feedback: list[str]
    generated: Annotated[dict[str, Any], _merge_dicts]
    summary: dict[str, Any]

    # WU-11
    verification: dict[str, Any]
    repair_round: int

    # WU-12
    resume: dict[str, Any]
    trace: dict[str, Any]
    generate_status: ResumeGenerateStatus
    errors: list[str]
