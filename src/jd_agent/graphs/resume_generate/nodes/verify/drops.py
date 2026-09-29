"""Drop failing highlights after repair rounds are exhausted."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def drop_failed_highlights(
    generated: dict[str, Any],
    failed_by_instance: dict[str, list[int]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Remove failing highlight indices; return updated ``generated`` and audit rows."""

    updated = deepcopy(generated)
    dropped: list[dict[str, Any]] = []

    for instance_id, indices in failed_by_instance.items():
        payload = updated.get(instance_id)
        if not isinstance(payload, dict):
            continue
        highlights = list(payload.get("highlights") or [])
        for index in sorted(set(indices), reverse=True):
            if 0 <= index < len(highlights):
                row = highlights.pop(index)
                dropped.append(
                    {
                        "instance_id": instance_id,
                        "index": index,
                        "text": row.get("text") if isinstance(row, dict) else str(row),
                    }
                )
        payload["highlights"] = highlights
        updated[instance_id] = payload

    return updated, dropped
