"""Fan-out helpers for parallel highlight generation."""

from __future__ import annotations

from typing import Any

from langgraph.types import Send

from jd_agent.graphs.resume_generate.models import InstanceBrief


def is_generatable_brief(raw: dict[str, Any]) -> bool:
    """True when this instance should invoke the highlight LLM."""
    brief = InstanceBrief.model_validate(raw)
    return brief.budget > 0 and bool(brief.atoms)


def generatable_instance_ids(briefs: dict[str, Any]) -> list[str]:
    """Ordered instance ids that need highlight generation."""
    instances = briefs.get("instances")
    if not isinstance(instances, dict):
        return []
    ordered = briefs.get("generatable_instance_ids")
    if isinstance(ordered, list) and ordered:
        return [
            str(iid)
            for iid in ordered
            if str(iid) in instances
            and isinstance(instances[str(iid)], dict)
            and is_generatable_brief(instances[str(iid)])
        ]
    return [
        iid
        for iid, raw in instances.items()
        if isinstance(raw, dict) and is_generatable_brief(raw)
    ]


def instances_to_generate(
    state: dict[str, Any],
    *,
    from_repair: bool,
) -> list[str]:
    """Instance ids for the next highlight fan-out."""
    briefs = state.get("briefs")
    if not isinstance(briefs, dict):
        return []

    candidates = generatable_instance_ids(briefs)
    if not candidates:
        return []

    if not from_repair:
        return candidates

    verification = state.get("verification")
    if not isinstance(verification, dict):
        return candidates

    failed = verification.get("failed_instances")
    if not isinstance(failed, list) or not failed:
        return candidates

    failed_set = {str(iid) for iid in failed}
    return [iid for iid in candidates if iid in failed_set]


def build_highlight_sends(
    state: dict[str, Any],
    *,
    from_repair: bool,
) -> list[Send]:
    """Build ``Send`` payloads; each branch writes one key into ``generated``."""
    briefs = state.get("briefs")
    if not isinstance(briefs, dict):
        return []

    instances = briefs.get("instances")
    if not isinstance(instances, dict):
        return []

    verification = state.get("verification")
    feedback_by_instance: dict[str, list[str]] = {}
    if isinstance(verification, dict):
        raw_feedback = verification.get("feedback")
        if isinstance(raw_feedback, dict):
            for iid, messages in raw_feedback.items():
                if isinstance(messages, list):
                    feedback_by_instance[str(iid)] = [str(m) for m in messages]
                elif messages:
                    feedback_by_instance[str(iid)] = [str(messages)]

    sends: list[Send] = []
    for instance_id in instances_to_generate(state, from_repair=from_repair):
        raw_brief = instances.get(instance_id)
        if not isinstance(raw_brief, dict):
            continue
        sends.append(
            Send(
                "generate_highlights",
                {
                    "brief": raw_brief,
                    "feedback": feedback_by_instance.get(instance_id, []),
                },
            )
        )
    return sends
