"""Unit tests for shared evidence parsing."""

from __future__ import annotations

from jd_agent.shared.evidence import parse_evidence


def test_parse_evidence_maps_confidence_strings() -> None:
    raw = '[{"evidenceText": "Built APIs.", "confidence": "high", "sourceKind": "resume"}]'
    entries = parse_evidence(raw)
    assert len(entries) == 1
    assert entries[0].evidenceText == "Built APIs."
    assert entries[0].confidence == 0.9
    assert entries[0].sourceKind == "resume"


def test_parse_evidence_accepts_list_payload() -> None:
    entries = parse_evidence([{"evidenceText": "x", "confidence": 1.0}])
    assert len(entries) == 1
    assert entries[0].confidence == 1.0
