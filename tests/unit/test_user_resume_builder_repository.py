"""Unit tests for the user_resume_builder repository."""

from __future__ import annotations

from typing import Any

from jd_agent.integrations.supabase import user_resume_builder_repository as urb


class _Resp:
    def __init__(self, data: Any, error: Any = None) -> None:
        self.data = data
        self.error = error


class _Builder:
    def __init__(self, base_row: dict[str, Any]) -> None:
        self._row = dict(base_row)
        self._single = False
        self.update_payload: dict[str, Any] | None = None

    def update(self, payload: dict[str, Any]) -> _Builder:
        self.update_payload = payload
        self._row.update(payload)
        return self

    def select(self, *_args: Any, **_kwargs: Any) -> _Builder:
        return self

    def eq(self, *_args: Any, **_kwargs: Any) -> _Builder:
        return self

    def maybe_single(self) -> _Builder:
        self._single = True
        return self

    def execute(self) -> _Resp:
        if self._single:
            return _Resp(self._row)
        return _Resp([self._row])


class _FakeClient:
    def __init__(self, base_row: dict[str, Any]) -> None:
        self.builder = _Builder(base_row)

    def table(self, _name: str) -> _Builder:
        return self.builder


_BASE = {
    "id": "sess-1",
    "user_id": "user-1",
    "status": "gap-analysis",
    "job_description_id": "jd-1",
    "interviewed": False,
    "gaps": None,
    "gaps_date": None,
    "created_at": "2026-09-21T00:00:00Z",
}


def test_normalize_defaults() -> None:
    row = urb.normalize_user_resume_builder({"id": "x", "user_id": "u"})
    assert row.status == urb.GAP_ANALYSIS_STEP
    assert row.interviewed is False
    assert row.gaps is None


def test_mark_gap_analysis_in_progress_sets_status() -> None:
    client = _FakeClient(_BASE)
    result = urb.mark_gap_analysis_in_progress(client, "sess-1")  # type: ignore[arg-type]
    assert client.builder.update_payload == {"status": urb.GAP_ANALYSIS_IN_PROGRESS}
    assert result.status == urb.GAP_ANALYSIS_IN_PROGRESS


def test_save_gaps_writes_payload_and_advances_step() -> None:
    client = _FakeClient(_BASE)
    gaps = {"schema_version": 1, "meta": {"fit": 0.5}}
    result = urb.save_gaps(client, "sess-1", gaps)  # type: ignore[arg-type]

    payload = client.builder.update_payload
    assert payload is not None
    assert payload["status"] == urb.GAP_INTERVIEW_STEP
    assert payload["gaps"] == gaps
    assert "gaps_date" in payload
    assert result.status == urb.GAP_INTERVIEW_STEP
