"""Deterministic verification rules for highlights and summary."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.constants import (
    BASICS_SUMMARY_MAX_WORDS,
    HIGHLIGHT_MAX_WORDS,
)
from jd_agent.graphs.resume_generate.models import (
    GeneratedHighlight,
    InstanceBrief,
    SummaryResult,
)
from jd_agent.graphs.resume_generate.nodes.verify.terms import (
    find_hidden_terms,
    jd_spans_for_scan,
)
from jd_agent.shared.resume_metrics import extract_metrics
from jd_agent.shared.resume_text import contains_first_person, leading_verb, word_count
from jd_agent.shared.summary_grounding import allowed_summary_numbers, allowed_summary_terms
from jd_agent.shared.text_match import token_jaccard

_PRESENT_LEADING = frozenset(
    {
        "lead",
        "leads",
        "manage",
        "manages",
        "build",
        "builds",
        "design",
        "designs",
        "develop",
        "develops",
        "architect",
        "architects",
        "drive",
        "drives",
        "deliver",
        "delivers",
    }
)

_DUPLICATE_JACCARD = 0.7


def _licensed_for_atoms(brief: InstanceBrief, atom_ids: list[str]) -> set[str]:
    by_id = {a.atom_id: a for a in brief.atoms}
    terms: set[str] = set()
    for aid in atom_ids:
        atom = by_id.get(aid)
        if atom is None:
            continue
        for term in atom.licensed:
            if term.strip():
                terms.add(term.strip())
    return terms


def _metrics_for_atoms(brief: InstanceBrief, atom_ids: list[str]) -> set[str]:
    by_id = {a.atom_id: a for a in brief.atoms}
    metrics: set[str] = set()
    for aid in atom_ids:
        atom = by_id.get(aid)
        if atom is None:
            continue
        for m in atom.metrics:
            if str(m).strip():
                metrics.add(str(m).strip())
    return metrics


def _tense_violation(brief: InstanceBrief, text: str) -> str | None:
    verb = leading_verb(text)
    if not verb:
        return None
    if brief.tense == "past" and verb in _PRESENT_LEADING:
        return f"expected past tense but leading verb is {verb!r}"
    if brief.tense == "present" and verb.endswith("ed") and len(verb) > 3:
        return f"expected present tense but leading verb looks past ({verb!r})"
    return None


def verify_highlight(
    brief: InstanceBrief,
    highlight: GeneratedHighlight,
    *,
    index: int,
    seen_verbs: set[str],
    jd_spans: list[tuple[str, str, Any]],
) -> list[str]:
    errors: list[str] = []
    prefix = f"highlight[{index}]"
    text = highlight.text.strip()
    if not text:
        return [f"{prefix}: empty text"]

    allowed_atoms = {a.atom_id for a in brief.atoms}
    atom_ids = list(highlight.atom_ids)

    if not atom_ids or len(atom_ids) > 2:
        errors.append(f"{prefix}: atom_ids must contain 1–2 ids, got {len(atom_ids)}")
    for aid in atom_ids:
        if aid not in allowed_atoms:
            errors.append(f"{prefix}: atom_id {aid!r} not in brief")

    licensed = _licensed_for_atoms(brief, atom_ids)
    for term in highlight.jd_terms_used:
        if term not in licensed:
            errors.append(f"{prefix}: jd term {term!r} not licensed for chosen atoms")

    for hidden in find_hidden_terms(text, jd_spans, licensed):
        errors.append(f"{prefix}: hidden unlicensed JD term {hidden!r}")

    allowed_metrics = _metrics_for_atoms(brief, atom_ids)
    for span in extract_metrics(text):
        if span not in allowed_metrics:
            errors.append(f"{prefix}: number {span!r} not in atom metrics")

    if word_count(text) > HIGHLIGHT_MAX_WORDS:
        errors.append(f"{prefix}: exceeds {HIGHLIGHT_MAX_WORDS} words")

    if contains_first_person(text):
        errors.append(f"{prefix}: first person not allowed")

    tense_err = _tense_violation(brief, text)
    if tense_err:
        errors.append(f"{prefix}: {tense_err}")

    verb = leading_verb(text)
    if verb:
        if verb in seen_verbs:
            errors.append(f"{prefix}: duplicate leading verb {verb!r}")
        seen_verbs.add(verb)

    return errors


def verify_instance_highlights(
    brief: InstanceBrief,
    highlights: list[GeneratedHighlight],
    *,
    jd_spans: list[tuple[str, str, Any]],
) -> list[str]:
    errors: list[str] = []
    if len(highlights) != brief.budget:
        errors.append(
            f"expected {brief.budget} highlights, got {len(highlights)}"
        )
    seen_verbs: set[str] = set()
    for index, highlight in enumerate(highlights):
        errors.extend(
            verify_highlight(
                brief,
                highlight,
                index=index,
                seen_verbs=seen_verbs,
                jd_spans=jd_spans,
            )
        )
    return errors


def verify_summary(
    summary: SummaryResult,
    *,
    context: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    text = summary.text.strip()
    if not text:
        return ["summary text is empty"]

    if word_count(text) > BASICS_SUMMARY_MAX_WORDS:
        errors.append(f"summary exceeds {BASICS_SUMMARY_MAX_WORDS} words")
    if contains_first_person(text):
        errors.append("summary uses first person")

    allowed_terms = allowed_summary_terms(
        context.get("generated") or {},
        context.get("static_skills") or [],
        skill_group_labels=context.get("skill_group_labels"),
    )
    for term in summary.claimed_terms:
        t = str(term).strip()
        if t and t not in allowed_terms:
            errors.append(f"claimed term {t!r} not allowed")

    allowed_numbers = allowed_summary_numbers(
        context.get("atoms") or [],
        context.get("selected_ids") or set(),
        context.get("years_facts") or {},
        (context.get("flagship_metric") or {}).get("metric")
        if isinstance(context.get("flagship_metric"), dict)
        else None,
    )
    for num in summary.claimed_numbers:
        n = str(num).strip()
        if n and n not in allowed_numbers:
            errors.append(f"claimed number {n!r} not allowed")

    flagship = context.get("flagship_metric")
    if isinstance(flagship, dict):
        metric = str(flagship.get("metric") or "").strip()
        if metric and metric not in text:
            errors.append(f"missing flagship metric {metric!r}")

    for span in extract_metrics(text):
        if span not in allowed_numbers:
            errors.append(f"number {span!r} in summary not allowed")

    return errors


def find_duplicate_lines(lines: list[str]) -> list[tuple[int, int, float]]:
    """Pairs of line indices with Jaccard >= threshold."""

    dupes: list[tuple[int, int, float]] = []
    for i, a in enumerate(lines):
        for j in range(i + 1, len(lines)):
            score = token_jaccard(a, lines[j])
            if score >= _DUPLICATE_JACCARD:
                dupes.append((i, j, score))
    return dupes


def build_jd_spans(
    jd_targets: list[dict[str, Any]],
    d_star: dict[str, float],
    skill_meta: dict[str, dict[str, str]],
) -> list[tuple[str, str, Any]]:
    return jd_spans_for_scan(jd_targets, d_star, skill_meta)
