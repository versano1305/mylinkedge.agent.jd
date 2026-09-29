"""WU-11 — Deterministic verification, repair routing, coverage, and gaps."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.constants import MAX_REPAIR_ROUNDS
from jd_agent.graphs.resume_generate.models import (
    GeneratedInstance,
    InstanceBrief,
    SummaryResult,
)
from jd_agent.graphs.resume_generate.nodes.generate_summary.context import (
    build_summary_context,
)
from jd_agent.graphs.resume_generate.feedback_keys import SUMMARY_FEEDBACK_KEY
from jd_agent.graphs.resume_generate.nodes.verify.checks import (
    build_jd_spans,
    find_duplicate_lines,
    verify_instance_highlights,
    verify_summary,
)
from jd_agent.graphs.resume_generate.nodes.verify.coverage import (
    compute_coverage,
    resume_text_blob,
)
from jd_agent.graphs.resume_generate.nodes.verify.drops import drop_failed_highlights
from jd_agent.graphs.resume_generate.nodes.verify.gaps import build_gap_report
from jd_agent.graphs.resume_generate.state import ResumeGenerateState
from jd_agent.integrations.skills_graph import get_skills_graph
from jd_agent.shared.summary_grounding import selected_atom_ids

_HIGHLIGHT_IDX = re.compile(r"highlight\[(\d+)\]")


def _run_verification(state: ResumeGenerateState) -> dict[str, Any]:
    briefs = state.get("briefs") if isinstance(state.get("briefs"), dict) else {}
    instances = briefs.get("instances") if isinstance(briefs.get("instances"), dict) else {}
    static = briefs.get("static") if isinstance(briefs.get("static"), dict) else {}
    static_skills = list(static.get("skills") or [])

    generated_raw = state.get("generated") if isinstance(state.get("generated"), dict) else {}
    demand = state.get("demand") if isinstance(state.get("demand"), dict) else {}
    d_star = {k: float(v) for k, v in (demand.get("d_star") or {}).items()}
    jd_targets = list(state.get("jd_targets") or [])

    skills_graph = get_skills_graph()
    skill_meta: dict[str, dict[str, str]] = {
        nid: {"name": node.name, "skillType": node.skill_type}
        for nid, node in skills_graph.nodes.items()
    }
    jd_spans = build_jd_spans(jd_targets, d_star, skill_meta)

    feedback: dict[str, list[str]] = {}
    failed_instances: list[str] = []
    failed_by_index: dict[str, list[int]] = {}
    failed_summary = False

    all_lines: list[str] = []
    line_refs: list[tuple[str, int]] = []

    for instance_id, raw_brief in instances.items():
        if not isinstance(raw_brief, dict):
            continue
        brief = InstanceBrief.model_validate(raw_brief)
        if brief.budget <= 0:
            continue
        payload_raw = generated_raw.get(instance_id) or {}
        payload = GeneratedInstance.model_validate(payload_raw)
        errors = verify_instance_highlights(
            brief, payload.highlights, jd_spans=jd_spans
        )
        for index, highlight in enumerate(payload.highlights):
            all_lines.append(highlight.text)
            line_refs.append((instance_id, index))
        if errors:
            failed_instances.append(str(instance_id))
            feedback[str(instance_id)] = errors

    dupes = find_duplicate_lines(all_lines)
    for i, j, score in dupes:
        inst_i, idx_i = line_refs[i]
        inst_j, idx_j = line_refs[j]
        message = (
            f"highlight near-duplicate (Jaccard {score:.2f}) with "
            f"{inst_j}[{idx_j}]"
        )
        feedback.setdefault(inst_i, []).append(f"highlight[{idx_i}]: {message}")
        failed_by_index.setdefault(inst_i, []).append(idx_i)
        if inst_i not in failed_instances:
            failed_instances.append(inst_i)

    summary_raw = state.get("summary") if isinstance(state.get("summary"), dict) else {}
    summary = SummaryResult.model_validate(summary_raw)
    summary_context = build_summary_context(state)
    summary_context["generated"] = generated_raw
    summary_context["static_skills"] = static_skills
    summary_context["skill_group_labels"] = list(briefs.get("skill_group_labels") or [])
    summary_context["atoms"] = list(state.get("atoms") or [])
    summary_context["years_facts"] = briefs.get("years_facts") or {}
    summary_context["selected_ids"] = selected_atom_ids(
        state.get("allocation") if isinstance(state.get("allocation"), dict) else {}
    )

    if summary.text.strip():
        summary_errors = verify_summary(summary, context=summary_context)
        if summary_errors:
            failed_summary = True
            feedback[SUMMARY_FEEDBACK_KEY] = summary_errors

    for instance_id, messages in list(feedback.items()):
        if instance_id == SUMMARY_FEEDBACK_KEY:
            continue
        indices: list[int] = []
        for msg in messages:
            match = _HIGHLIGHT_IDX.search(msg)
            if match:
                indices.append(int(match.group(1)))
        if indices:
            failed_by_index[instance_id] = sorted(set(indices))

    summary_text = summary.text.strip()
    resume_blob = resume_text_blob(generated_raw, summary_text, static_skills)
    coverage = compute_coverage(jd_targets, d_star, resume_blob)
    allocation = state.get("allocation") if isinstance(state.get("allocation"), dict) else {}
    covered_ids = set(allocation.get("covered_jd_skill_ids") or [])
    gap_report = build_gap_report(
        jd_targets,
        demand,
        list(state.get("atoms") or []),
        resume_blob,
        covered_ids,
    )

    needs_repair = bool(failed_instances or failed_summary)
    return {
        "feedback": feedback,
        "failed_instances": failed_instances,
        "failed_summary": failed_summary,
        "failed_by_index": failed_by_index,
        "needs_repair": needs_repair,
        "coverage": coverage,
        "gap_report": gap_report,
        "passed": not needs_repair,
    }


def verify(state: ResumeGenerateState, config: RunnableConfig) -> dict[str, Any]:
    _ = config
    repair_round = int(state.get("repair_round") or 0)
    generated_raw = state.get("generated") if isinstance(state.get("generated"), dict) else {}

    result = _run_verification(state)
    needs_repair = bool(result.pop("needs_repair"))
    failed_by_index = result.pop("failed_by_index")
    dropped: list[dict[str, Any]] = []
    out_generated: dict[str, Any] | None = None

    if needs_repair:
        if repair_round < MAX_REPAIR_ROUNDS:
            repair_round += 1
        else:
            out_generated, dropped = drop_failed_highlights(generated_raw, failed_by_index)
            result["failed_instances"] = []
            result["failed_summary"] = False
            result["feedback"] = {}
            result["passed"] = True
            needs_repair = False

    verification = {
        **result,
        "needs_repair": needs_repair,
        "dropped_lines": dropped,
    }
    payload: dict[str, Any] = {
        "verification": verification,
        "repair_round": repair_round,
    }
    if out_generated is not None:
        payload["generated"] = out_generated
    return payload
