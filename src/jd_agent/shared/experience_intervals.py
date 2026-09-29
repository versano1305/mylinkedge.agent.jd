"""Merge employment date ranges for years-of-experience (WU-08 / WU-10)."""

from __future__ import annotations

from datetime import date
from typing import Iterable


def parse_ym(raw: str | None) -> tuple[int, int] | None:
    """Parse ``YYYY-MM``; return ``None`` when invalid or missing."""

    if not raw:
        return None
    parts = str(raw).split("-", 1)
    if len(parts) != 2:
        return None
    try:
        y, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (1 <= m <= 12):
        return None
    return y, m


def _end_ym(end: str | None, *, today: date | None = None) -> tuple[int, int] | None:
    parsed = parse_ym(end)
    if parsed is not None:
        return parsed
    if end is None:
        ref = today or date.today()
        return ref.year, ref.month
    return None


def months_between(start: tuple[int, int], end: tuple[int, int]) -> float:
    """Inclusive month span from start month through end month."""

    sy, sm = start
    ey, em = end
    return float((ey - sy) * 12 + (em - sm) + 1)


def merge_intervals(
    ranges: Iterable[tuple[tuple[int, int], tuple[int, int]]],
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Merge overlapping ``(start, end)`` month ranges (both inclusive)."""

    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    merged: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for start, end in sorted_ranges:
        if merged and start <= merged[-1][1]:
            prev_start, prev_end = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end, key=_ym_key))
        else:
            merged.append((start, end))
    return merged


def _ym_key(ym: tuple[int, int]) -> tuple[int, int]:
    return ym


def union_months(
    ranges: Iterable[tuple[tuple[int, int], tuple[int, int]]],
) -> float:
    """Total months after merging overlaps (do not sum concurrent roles)."""

    merged = merge_intervals(ranges)
    return sum(months_between(s, e) for s, e in merged)


def union_years(
    ranges: Iterable[tuple[tuple[int, int], tuple[int, int]]],
) -> float:
    return union_months(ranges) / 12.0


def experience_range(
    start: str | None,
    end: str | None,
    *,
    today: date | None = None,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """One role interval, or ``None`` when start is missing or unparsable."""

    start_ym = parse_ym(start)
    if start_ym is None:
        return None
    end_ym = _end_ym(end, today=today)
    if end_ym is None:
        return None
    if _ym_key(end_ym) < _ym_key(start_ym):
        return None
    return start_ym, end_ym
