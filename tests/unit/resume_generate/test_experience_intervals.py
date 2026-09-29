"""Tests for shared experience interval merging."""

from __future__ import annotations

from jd_agent.shared.experience_intervals import union_months, union_years


def test_union_months_merges_overlap() -> None:
    ranges = [
        ((2019, 3), (2021, 12)),
        ((2022, 1), (2024, 6)),
    ]
    months = union_months(ranges)
    assert months > 0
    assert union_years(ranges) == months / 12.0


def test_union_months_does_not_double_concurrent_roles() -> None:
    concurrent = [
        ((2020, 1), (2022, 1)),
        ((2020, 6), (2021, 6)),
    ]
    single = [((2020, 1), (2022, 1))]
    assert union_months(concurrent) == union_months(single)
