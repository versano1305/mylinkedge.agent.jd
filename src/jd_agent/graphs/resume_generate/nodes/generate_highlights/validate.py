"""In-node validation before returning generated highlights."""

from __future__ import annotations

from jd_agent.graphs.resume_generate.constants import (
    HIGHLIGHT_MAX_WORDS,
    SUMMARY_MAX_WORDS,
)
from jd_agent.graphs.resume_generate.models import (
    GeneratedHighlight,
    InstanceBrief,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.models import (
    HighlightGenerationResult,
)
from jd_agent.shared.resume_text import word_count


def _allowed_atom_ids(brief: InstanceBrief) -> set[str]:
    return {a.atom_id for a in brief.atoms}


def _licensed_terms_for_atoms(brief: InstanceBrief, atom_ids: list[str]) -> set[str]:
    allowed_atoms = {a.atom_id: a for a in brief.atoms}
    terms: set[str] = set()
    for aid in atom_ids:
        atom = allowed_atoms.get(aid)
        if atom is None:
            continue
        for term in atom.licensed:
            if term.strip():
                terms.add(term)
    return terms


def validate_generation(
    brief: InstanceBrief,
    result: HighlightGenerationResult,
) -> list[str]:
    """Return human-readable violations; empty list means the payload is acceptable."""
    errors: list[str] = []
    allowed_atoms = _allowed_atom_ids(brief)

    if brief.budget <= 0:
        if result.highlights or result.summary.strip():
            errors.append("expected no highlights or summary when budget is zero")
        return errors

    if len(result.highlights) != brief.budget:
        errors.append(
            f"expected exactly {brief.budget} highlights, got {len(result.highlights)}"
        )

    if result.summary.strip() and word_count(result.summary) > SUMMARY_MAX_WORDS:
        errors.append(
            f"summary exceeds {SUMMARY_MAX_WORDS} words ({word_count(result.summary)})"
        )

    seen_verbs: set[str] = set()
    for index, highlight in enumerate(result.highlights):
        errors.extend(
            _validate_highlight(brief, highlight, index, allowed_atoms, seen_verbs)
        )

    return errors


def _validate_highlight(
    brief: InstanceBrief,
    highlight: GeneratedHighlight,
    index: int,
    allowed_atoms: set[str],
    seen_verbs: set[str],
) -> list[str]:
    errors: list[str] = []
    prefix = f"highlight[{index}]"

    if not highlight.text.strip():
        errors.append(f"{prefix}: empty text")
        return errors

    if word_count(highlight.text) > HIGHLIGHT_MAX_WORDS:
        errors.append(
            f"{prefix}: exceeds {HIGHLIGHT_MAX_WORDS} words ({word_count(highlight.text)})"
        )

    atom_ids = list(highlight.atom_ids)
    if not atom_ids or len(atom_ids) > 2:
        errors.append(f"{prefix}: atom_ids must contain 1–2 ids, got {len(atom_ids)}")

    for aid in atom_ids:
        if aid not in allowed_atoms:
            errors.append(f"{prefix}: atom_id {aid!r} not in brief")

    allowed_terms = _licensed_terms_for_atoms(brief, atom_ids)
    for term in highlight.jd_terms_used:
        if term not in allowed_terms:
            errors.append(f"{prefix}: jd term {term!r} not licensed for chosen atoms")

    first = highlight.text.strip().split()[0].lower() if highlight.text.strip() else ""
    if first:
        if first in seen_verbs:
            errors.append(f"{prefix}: duplicate leading verb {first!r}")
        seen_verbs.add(first)

    return errors
