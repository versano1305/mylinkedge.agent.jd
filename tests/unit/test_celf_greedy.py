"""Tests for lazy greedy (CELF) selection."""

from __future__ import annotations

from jd_agent.shared.celf_greedy import celf_greedy_select, naive_greedy_select


def _coverage_gain(item: str, selected: set[str]) -> float:
    """Each item covers one skill; overlapping items add no gain."""

    covered: set[str] = set(selected)
    if item in covered:
        return 0.0
    return 1.0


def test_celf_matches_naive_greedy() -> None:
    candidates = ["a", "b", "c", "a"]
    celf = celf_greedy_select(
        list(dict.fromkeys(candidates)),
        _coverage_gain,
        max_items=3,
        min_gain=0.0,
    )
    naive = naive_greedy_select(
        list(dict.fromkeys(candidates)),
        _coverage_gain,
        max_items=3,
        min_gain=0.0,
    )
    assert celf == naive
