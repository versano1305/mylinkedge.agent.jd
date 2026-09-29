"""Lazy greedy (CELF) for monotone submodular maximization under a cardinality cap.

Used when marginal gains are expensive to evaluate (e.g. resume fit). For
allocation with per-instance budgets, see ``allocate/select.py`` constrained
greedy instead.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable, Hashable


def celf_greedy_select(
    candidates: list[Hashable],
    marginal_gain: Callable[[Hashable, set[Hashable]], float],
    *,
    max_items: int,
    min_gain: float = 0.0,
) -> list[Hashable]:
    """Return up to ``max_items`` items greedily maximizing summed marginal gain.

    ``marginal_gain(item, selected)`` must be non-increasing as ``selected``
    grows for CELF to be exact; when in doubt use ``naive_greedy_select``.
    """

    selected: set[Hashable] = set()
    order: list[Hashable] = []
    if max_items <= 0 or not candidates:
        return order

    # (negative gain for max-heap, last_evaluated_round, item)
    heap: list[tuple[float, int, Hashable]] = []
    round_idx = 0
    for item in candidates:
        gain = marginal_gain(item, selected)
        heapq.heappush(heap, (-gain, round_idx, item))

    while heap and len(order) < max_items:
        round_idx += 1
        while heap:
            neg_gain, last_round, item = heapq.heappop(heap)
            if item in selected:
                continue
            if last_round != round_idx:
                gain = marginal_gain(item, selected)
                heapq.heappush(heap, (-gain, round_idx, item))
                continue
            gain = -neg_gain
            if gain < min_gain:
                return order
            selected.add(item)
            order.append(item)
            break
        else:
            break
    return order


def naive_greedy_select(
    candidates: list[Hashable],
    marginal_gain: Callable[[Hashable, set[Hashable]], float],
    *,
    max_items: int,
    min_gain: float = 0.0,
) -> list[Hashable]:
    """Unconstrained greedy; reference for CELF tests."""

    selected: set[Hashable] = set()
    order: list[Hashable] = []
    remaining = list(candidates)
    while remaining and len(order) < max_items:
        best_item = max(remaining, key=lambda c: marginal_gain(c, selected))
        gain = marginal_gain(best_item, selected)
        if gain < min_gain:
            break
        selected.add(best_item)
        order.append(best_item)
        remaining.remove(best_item)
    return order
