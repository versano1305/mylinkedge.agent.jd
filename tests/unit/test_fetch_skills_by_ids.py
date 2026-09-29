"""Unit tests for batch Skill property lookup."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from jd_agent.integrations.skills_graph.skill_details import fetch_skills_by_ids


class _Session:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object]]] = []

    def run(self, query: str, **kwargs: object) -> list[dict[str, str]]:
        self.calls.append((query, kwargs))
        return self.rows

    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


class _Driver:
    def __init__(self, session: _Session) -> None:
        self._session = session
        self.databases: list[str | None] = []

    def session(self, database: str | None = None) -> _Session:
        self.databases.append(database)
        return self._session


def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jd_agent.integrations.skills_graph.skill_details.Neo4jSettings.from_env",
        lambda: SimpleNamespace(resolved_data_database="skills-data"),
    )


def test_fetch_skills_by_ids_projects_only_requested_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _Session([{"id": "skill-a", "name": "Alpha", "skillType": "Tool"}])
    driver = _Driver(session)
    _patch_settings(monkeypatch)

    found = fetch_skills_by_ids(
        ["skill-a", " skill-a ", ""],
        ("id", "name", "skillType"),
        driver=driver,  # type: ignore[arg-type]
    )

    assert found == {"skill-a": {"id": "skill-a", "name": "Alpha", "skillType": "Tool"}}
    assert driver.databases == ["skills-data"]
    query, params = session.calls[0]
    assert params == {"skill_ids": ["skill-a"]}
    assert "s.id AS id" in query
    assert "coalesce(s.name, '') AS name" in query
    assert "coalesce(s.skillType, '') AS skillType" in query
    assert "skill_type" not in query


def test_fetch_skills_by_ids_omits_fields_not_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _Session([{"id": "skill-a", "name": "Alpha"}])
    driver = _Driver(session)
    _patch_settings(monkeypatch)

    fetch_skills_by_ids(
        ["skill-a"],
        ("name", "id"),
        driver=driver,  # type: ignore[arg-type]
    )

    query = session.calls[0][0]
    assert "s.id AS id" in query
    assert "coalesce(s.name, '') AS name" in query
    assert "skillType" not in query


def test_fetch_skills_by_ids_empty_ids_does_not_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _Session([])
    driver = _Driver(session)
    called = False

    def _from_env() -> SimpleNamespace:
        nonlocal called
        called = True
        return SimpleNamespace(resolved_data_database="skills-data")

    monkeypatch.setattr(
        "jd_agent.integrations.skills_graph.skill_details.Neo4jSettings.from_env",
        _from_env,
    )

    assert fetch_skills_by_ids(["", "  "], ("id", "name"), driver=driver) == {}  # type: ignore[arg-type]
    assert session.calls == []
    assert driver.databases == []
    assert called is False


def test_fetch_skills_by_ids_rejects_unknown_or_empty_fields() -> None:
    with pytest.raises(ValueError, match="unsupported skill field"):
        fetch_skills_by_ids(["skill-a"], ("id", "description"))
    with pytest.raises(ValueError, match="at least one"):
        fetch_skills_by_ids(["skill-a"], ())
    with pytest.raises(ValueError, match="must include 'id'"):
        fetch_skills_by_ids(["skill-a"], ("name", "skillType"))
