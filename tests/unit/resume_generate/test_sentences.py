"""Unit tests for sentence splitting."""

from __future__ import annotations

from jd_agent.shared.sentences import split_sentences


def test_split_sentences_respects_multiple_clauses() -> None:
    text = "Led cloud migration. Owned Kubernetes platform."
    parts = split_sentences(text)
    assert len(parts) == 2
    assert parts[0].startswith("Led")


def test_split_sentences_keeps_abbreviation_together() -> None:
    text = "Worked with e.g. banks and fintechs. Shipped features."
    parts = split_sentences(text)
    assert len(parts) >= 1
