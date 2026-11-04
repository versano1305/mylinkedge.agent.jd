"""JD agent HTTP thread API (unit tests with stub graph)."""

from __future__ import annotations

from typing import TypedDict

import httpx
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from mylinkedge_agent_tools.langgraph_streaming.grpc.registry import GraphRegistry, GraphSpec
from mylinkedge_agent_tools.langgraph_streaming.http import HttpSettings, create_app
from mylinkedge_agent_tools.langgraph_streaming.http.auth import mint_session_token


class StubState(TypedDict, total=False):
    jd_id: str
    extraction_status: str


def _stub_jd_graph():
    def mark_done(state: StubState) -> StubState:
        return {"extraction_status": "done"}

    builder = StateGraph(StubState)
    builder.add_node("mark_done", mark_done)
    builder.add_edge(START, "mark_done")
    builder.add_edge("mark_done", END)
    return builder.compile(checkpointer=MemorySaver())


@pytest.fixture
def http_settings(monkeypatch: pytest.MonkeyPatch) -> HttpSettings:
    monkeypatch.setenv("SERVICE_SECRET", "jd-test-service-secret")
    monkeypatch.setenv("SESSION_JWT_SECRET", "jd-test-jwt-secret-min-32-chars-long")
    return HttpSettings.from_env()


@pytest.fixture
def api_app(http_settings: HttpSettings):
    registry = GraphRegistry()
    registry.register(
        "jd_extract",
        GraphSpec(
            graph=_stub_jd_graph(),
            bootstrap_input=lambda body: {"jd_id": str(body["jd_id"])},
            state_keys=("extraction_status", "jd_id"),
        ),
    )
    return create_app(registry, http_settings)


@pytest.fixture
async def client(api_app):
    transport = httpx.ASGITransport(app=api_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_thread_rejects_missing_secret(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/threads",
        json={
            "graph_id": "jd_extract",
            "sub": "user:1",
            "context": {"jd_id": "jd-1"},
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_thread_unknown_graph(
    client: httpx.AsyncClient,
    http_settings: HttpSettings,
) -> None:
    response = await client.post(
        "/threads",
        json={"graph_id": "missing", "sub": "user:1", "context": {}},
        headers={"X-Service-Secret": http_settings.service_secret},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_seed_and_stream_jd_extract_stub(
    client: httpx.AsyncClient,
    http_settings: HttpSettings,
) -> None:
    create = await client.post(
        "/threads",
        json={
            "graph_id": "jd_extract",
            "sub": "user:abc",
            "context": {"jd_id": "jd-99"},
        },
        headers={"X-Service-Secret": http_settings.service_secret},
    )
    assert create.status_code == 200
    thread_id = create.json()["thread_id"]

    token = mint_session_token(
        http_settings,
        sub="user:abc",
        thread_id=thread_id,
        graph_id="jd_extract",
    )
    async with client.stream(
        "POST",
        f"/threads/{thread_id}/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    ) as response:
        assert response.status_code == 200
        body = (await response.aread()).decode()
        assert "event: done" in body

    wrong_token = mint_session_token(
        http_settings,
        sub="user:abc",
        thread_id="other",
        graph_id="jd_extract",
    )
    forbidden = await client.post(
        f"/threads/{thread_id}/stream",
        headers={"Authorization": f"Bearer {wrong_token}"},
        json={},
    )
    assert forbidden.status_code == 403
