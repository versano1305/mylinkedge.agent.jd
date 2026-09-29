"""Build ``ResumeTrace`` provenance from graph state."""

from __future__ import annotations

from typing import Any

from mylinkedge_agent_tools.postgres import JobDescription, UserResumeBuilder

from jd_agent.graphs.resume_generate.constants import trace_constants
from jd_agent.graphs.resume_generate.models import (
    Allocation,
    CoverageReport,
    GapReportEntry,
    GeneratedInstance,
    ResumeTrace,
    SummaryResult,
    TraceFit,
    TraceLineProvenance,
    TraceMeta,
)
from jd_agent.graphs.resume_generate.nodes.assemble_and_save.resume_document import (
    build_work_entries,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def _session_gaps_fit(
    session: UserResumeBuilder | None, key: str = "fit"
) -> float | None:
    if session is None:
        return None
    gaps = session.gaps
    if not isinstance(gaps, dict):
        return None
    meta = gaps.get("meta")
    if not isinstance(meta, dict):
        return None
    fit = meta.get(key)
    return float(fit) if isinstance(fit, (int, float)) else None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _jd_enriched(jd: JobDescription | None) -> bool:
    if jd is None:
        return False
    for skill in jd.skills or []:
        data = skill.model_dump()
        if str(data.get("evidence_sentence") or "").strip():
            return True
        if data.get("min_years") is not None:
            return True
        if data.get("substitutable") is True:
            return True
    return False


def _atom_by_id(atoms: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(a["atom_id"]): a
        for a in atoms
        if isinstance(a, dict) and a.get("atom_id")
    }


def _line_provenance(
    highlight: dict[str, Any],
    atoms_by_id: dict[str, dict[str, Any]],
    repair_rounds: int,
) -> TraceLineProvenance:
    atom_ids = [str(a) for a in (highlight.get("atom_ids") or []) if str(a).strip()]
    jd_terms = [str(t) for t in (highlight.get("jd_terms_used") or []) if str(t).strip()]

    node_ids: list[str] = []
    jd_skill_ids: list[str] = []
    licensed_via: dict[str, str] = {}

    for aid in atom_ids:
        atom = atoms_by_id.get(aid)
        if not atom:
            continue
        for nid in atom.get("node_ids") or []:
            s = str(nid).strip()
            if s and s not in node_ids:
                node_ids.append(s)
        for term in atom.get("licensed") or []:
            if not isinstance(term, dict):
                continue
            surface = str(term.get("surface_form") or "").strip()
            jid = str(term.get("jd_skill_id") or "").strip()
            via = str(term.get("via") or "implied")
            if surface in jd_terms and surface not in licensed_via:
                licensed_via[surface] = via
            if jid and jid not in jd_skill_ids:
                jd_skill_ids.append(jid)

    return TraceLineProvenance(
        atom_ids=atom_ids,
        node_ids=node_ids,
        jd_skill_ids=jd_skill_ids,
        licensed_via=licensed_via,
        repair_rounds=repair_rounds,
    )


def build_trace_lines(
    allocation: Allocation,
    instance_briefs: dict[str, Any],
    generated: dict[str, Any],
    atoms: list[dict[str, Any]],
    summary: SummaryResult,
    repair_round: int,
) -> dict[str, TraceLineProvenance]:
    atoms_by_id = _atom_by_id(atoms)
    lines: dict[str, TraceLineProvenance] = {}

    work = build_work_entries(allocation, instance_briefs, generated)
    for work_index, row in enumerate(work):
        instance_id = row.instance_id or ""
        payload_raw = generated.get(instance_id) or {}
        payload = GeneratedInstance.model_validate(payload_raw)
        for hi, highlight in enumerate(payload.highlights):
            key = f"work[{work_index}].highlights[{hi}]"
            lines[key] = _line_provenance(
                highlight.model_dump(),
                atoms_by_id,
                repair_round,
            )

    if summary.text.strip():
        lines["basics.summary"] = TraceLineProvenance(
            claimed_terms=list(summary.claimed_terms),
            claimed_numbers=list(summary.claimed_numbers),
            repair_rounds=repair_round,
        )

    return lines


def build_trace_document(state: ResumeGenerateState) -> ResumeTrace:
    """Compose the full trace payload for persistence."""

    briefs = state.get("briefs") if isinstance(state.get("briefs"), dict) else {}
    instances = briefs.get("instances") if isinstance(briefs.get("instances"), dict) else {}
    jd_context = state.get("jd_context") if isinstance(state.get("jd_context"), dict) else {}

    allocation = Allocation.model_validate(
        state.get("allocation") if isinstance(state.get("allocation"), dict) else {}
    )
    demand = state.get("demand") if isinstance(state.get("demand"), dict) else {}
    verification = (
        state.get("verification") if isinstance(state.get("verification"), dict) else {}
    )
    generated = state.get("generated") if isinstance(state.get("generated"), dict) else {}
    atoms = list(state.get("atoms") or [])
    summary = SummaryResult.model_validate(
        state.get("summary") if isinstance(state.get("summary"), dict) else {}
    )
    repair_round = int(state.get("repair_round") or 0)

    session = state.get("session")
    jd = state.get("jd")
    user_id = str(state.get("user_id") or "")
    job_description_id = ""
    interviewed = False
    if isinstance(session, UserResumeBuilder):
        job_description_id = str(session.job_description_id or "")
        interviewed = bool(session.interviewed)

    unresolved = jd_context.get("unresolved")
    if not isinstance(unresolved, list):
        unresolved = []

    session_for_fit = session if isinstance(session, UserResumeBuilder) else None
    ontology = demand.get("ontology")
    fit = TraceFit(
        before_interview=_session_gaps_fit(session_for_fit),
        profile=_number(demand.get("fit_profile")),
        resume=float(allocation.resume_fit) if allocation.resume_fit else None,
        before_interview_normalized=_session_gaps_fit(session_for_fit, "fit_normalized"),
        profile_baseline=_number(demand.get("fit_profile_baseline")),
        profile_normalized=_number(demand.get("fit_profile_normalized")),
        resume_baseline=allocation.resume_fit_baseline,
        resume_normalized=allocation.resume_fit_normalized,
        ontology=ontology if isinstance(ontology, dict) else None,
    )

    coverage_raw = verification.get("coverage")
    coverage = (
        CoverageReport.model_validate(coverage_raw)
        if isinstance(coverage_raw, dict)
        else CoverageReport()
    )

    gap_raw = verification.get("gap_report")
    gap_report: list[GapReportEntry] = []
    if isinstance(gap_raw, list):
        for row in gap_raw:
            if isinstance(row, dict):
                gap_report.append(GapReportEntry.model_validate(row))

    dropped = verification.get("dropped_lines")
    dropped_lines = list(dropped) if isinstance(dropped, list) else []

    skills_sources = briefs.get("skills_sources")
    if not isinstance(skills_sources, dict):
        skills_sources = {}

    return ResumeTrace(
        meta=TraceMeta(
            user_id=user_id,
            job_description_id=job_description_id,
            interviewed=interviewed,
            jd_enriched=_jd_enriched(jd if isinstance(jd, JobDescription) else None),
            unresolved=[str(u) for u in unresolved if str(u).strip()],
            constants=trace_constants(),
        ),
        fit=fit,
        lines=build_trace_lines(
            allocation,
            instances,
            generated,
            atoms,
            summary,
            repair_round,
        ),
        skills_sources={
            str(k): [str(x) for x in v if str(x).strip()]
            for k, v in skills_sources.items()
            if isinstance(v, list)
        },
        coverage=coverage,
        gap_report=gap_report,
        dropped_lines=dropped_lines,
    )
