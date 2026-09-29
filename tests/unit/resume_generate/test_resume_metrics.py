"""Unit tests for metric extraction."""

from __future__ import annotations

from jd_agent.shared.resume_metrics import extract_metrics


def test_extract_metrics_finds_percent_and_currency() -> None:
    text = "Cut latency by 40% and saved $2.5m annually."
    found = extract_metrics(text)
    assert "40%" in found
    assert any("$" in m for m in found)


def test_extract_metrics_includes_impact_value_extra() -> None:
    found = extract_metrics("Improved reliability.", extra="99.7%")
    assert "99.7%" in found
