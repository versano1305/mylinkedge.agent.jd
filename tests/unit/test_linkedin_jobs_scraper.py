"""Unit tests for Bright Data LinkedIn Jobs scraper client and mapper."""

from __future__ import annotations

import json

import httpx
import pytest

from jd_agent.integrations.linkedin_jobs_scraper import (
    LinkedInJobsScraperClient,
    LinkedInJobsScraperError,
    LinkedInJobsScraperSettings,
    is_linkedin_job_url,
    map_brightdata_item_to_job_posting,
)


def _settings(**overrides: object) -> LinkedInJobsScraperSettings:
    base: dict[str, object] = {
        "api_token": "test-token",
        "base_url": "https://api.brightdata.test",
        "dataset_id": "gd_lpfll7v5hcqtkxl6l",
        "timeout_seconds": 5.0,
    }
    base.update(overrides)
    return LinkedInJobsScraperSettings(**base)  # type: ignore[arg-type]


def _client_with_handler(
    handler: object,
    *,
    settings: LinkedInJobsScraperSettings | None = None,
) -> LinkedInJobsScraperClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    http_client = httpx.Client(
        transport=transport, base_url="https://api.brightdata.test"
    )
    return LinkedInJobsScraperClient(settings or _settings(), client=http_client)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.linkedin.com/jobs/view/123", True),
        ("https://linkedin.com/jobs/view/123", True),
        ("https://il.linkedin.com/jobs/view/123", True),
        ("https://boards.greenhouse.io/acme/jobs/1", False),
        ("", False),
    ],
)
def test_is_linkedin_job_url(url: str, expected: bool) -> None:
    assert is_linkedin_job_url(url) is expected


def test_map_brightdata_item_to_job_posting() -> None:
    posting = map_brightdata_item_to_job_posting(
        {
            "url": "https://www.linkedin.com/jobs/view/123",
            "job_summary": "  We need a senior engineer.  ",
            "job_title": "SWE",
            "company_name": "Acme",
            "job_location": "Remote",
            "company_id": "2646",
        },
        url="https://www.linkedin.com/jobs/view/fallback",
        source="linkedin",
    )
    assert posting.description == "We need a senior engineer."
    assert posting.title == "SWE"
    assert posting.company_name == "Acme"
    assert posting.location == "Remote"
    assert posting.url == "https://www.linkedin.com/jobs/view/123"
    assert posting.source == "linkedin"
    assert "company_id" not in posting.model_fields


def test_map_brightdata_item_missing_summary() -> None:
    with pytest.raises(ValueError, match="job_summary"):
        map_brightdata_item_to_job_posting(
            {"job_title": "SWE"},
            url="https://www.linkedin.com/jobs/view/123",
        )


def test_fetch_job_posting_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/datasets/v3/scrape"
        assert request.url.params.get("dataset_id") == "gd_lpfll7v5hcqtkxl6l"
        assert request.url.params.get("format") == "json"
        assert request.headers.get("Authorization") == "Bearer test-token"
        body = json.loads(request.content.decode())
        assert body == {
            "input": [{"url": "https://www.linkedin.com/jobs/view/123"}],
        }
        return httpx.Response(
            200,
            json=[
                {
                    "job_summary": "  We need a senior engineer.  ",
                    "job_title": "SWE",
                    "company_name": "Acme",
                    "job_location": "NYC",
                }
            ],
        )

    with _client_with_handler(handler) as client:
        posting = client.fetch_job_posting("https://www.linkedin.com/jobs/view/123")
    assert posting.description == "We need a senior engineer."
    assert posting.title == "SWE"
    assert posting.company_name == "Acme"
    assert posting.location == "NYC"
    assert posting.source == "linkedin"


def test_fetch_job_posting_missing_token() -> None:
    client = LinkedInJobsScraperClient(_settings(api_token=""))
    with pytest.raises(RuntimeError, match="BRIGHTDATA_API_TOKEN"):
        client.fetch_job_posting("https://www.linkedin.com/jobs/view/123")


def test_fetch_job_posting_empty_dataset() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    with _client_with_handler(handler) as client:
        with pytest.raises(LinkedInJobsScraperError, match="no results"):
            client.fetch_job_posting("https://www.linkedin.com/jobs/view/123")


def test_fetch_job_posting_missing_summary() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"job_title": "SWE"}])

    with _client_with_handler(handler) as client:
        with pytest.raises(LinkedInJobsScraperError, match="job_summary"):
            client.fetch_job_posting("https://www.linkedin.com/jobs/view/123")


def test_fetch_job_posting_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized")

    with _client_with_handler(handler) as client:
        with pytest.raises(LinkedInJobsScraperError, match="HTTP 401"):
            client.fetch_job_posting("https://www.linkedin.com/jobs/view/123")


def test_fetch_job_posting_async_202() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"snapshot_id": "snap-1"})

    with _client_with_handler(handler) as client:
        with pytest.raises(LinkedInJobsScraperError, match="HTTP 202"):
            client.fetch_job_posting("https://www.linkedin.com/jobs/view/123")


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "tok")
    monkeypatch.setenv("BRIGHTDATA_BASE_URL", "https://example.test")
    monkeypatch.setenv("BRIGHTDATA_LINKEDIN_JOBS_DATASET_ID", "gd_custom")
    monkeypatch.setenv("BRIGHTDATA_TIMEOUT_SECONDS", "60")
    settings = LinkedInJobsScraperSettings.from_env()
    assert settings.api_token == "tok"
    assert settings.base_url == "https://example.test"
    assert settings.dataset_id == "gd_custom"
    assert settings.timeout_seconds == 60.0
