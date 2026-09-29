"""Sync httpx client for Bright Data LinkedIn Jobs (collect by URL).

API reference:
https://docs.brightdata.com/api-reference/scrapers/social-media-apis/linkedin-jobs-collect-by-url
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from jd_agent.integrations.linkedin_jobs_scraper.mapper import (
    map_brightdata_item_to_job_posting,
)
from jd_agent.integrations.linkedin_jobs_scraper.settings import (
    LinkedInJobsScraperSettings,
)
from jd_agent.shared.schemas import JobPosting


class LinkedInJobsScraperError(RuntimeError):
    """Raised when the Bright Data LinkedIn Jobs scrape call fails."""


def is_linkedin_job_url(url: str) -> bool:
    """Return True when ``url`` points at a linkedin.com host."""
    raw = (url or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return host == "linkedin.com" or host.endswith(".linkedin.com")


class LinkedInJobsScraperClient:
    """Fetch a single LinkedIn job posting via Bright Data scrape API."""

    def __init__(
        self,
        settings: LinkedInJobsScraperSettings | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or LinkedInJobsScraperSettings.from_env()
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=self._settings.timeout_seconds)

    @property
    def settings(self) -> LinkedInJobsScraperSettings:
        return self._settings

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> LinkedInJobsScraperClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_job_posting(self, url: str) -> JobPosting:
        """Scrape ``url`` and return a generic ``JobPosting``.

        Raises
        ------
        RuntimeError
            If ``BRIGHTDATA_API_TOKEN`` is not configured.
        LinkedInJobsScraperError
            On HTTP failure, async/timeout (202), empty dataset, or missing
            ``job_summary``.
        """
        token = (self._settings.api_token or "").strip()
        if not token:
            raise RuntimeError(
                "BRIGHTDATA_API_TOKEN is not configured for LinkedInJobsScraperClient."
            )

        job_url = (url or "").strip()
        if not job_url:
            raise LinkedInJobsScraperError("LinkedIn job URL is empty.")

        endpoint = f"{self._settings.base_url.rstrip('/')}/datasets/v3/scrape"
        params = {
            "dataset_id": self._settings.dataset_id,
            "format": "json",
            "include_errors": "true",
        }
        body: dict[str, Any] = {"input": [{"url": job_url}]}
        try:
            response = self._client.post(
                endpoint,
                params=params,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise LinkedInJobsScraperError(
                f"Bright Data LinkedIn Jobs request failed: {exc}"
            ) from exc

        if response.status_code == 202:
            snapshot_id = ""
            try:
                pending = response.json()
                if isinstance(pending, dict):
                    snapshot_id = str(pending.get("snapshot_id") or "").strip()
            except ValueError:
                snapshot_id = ""
            detail = f" snapshot_id={snapshot_id}" if snapshot_id else ""
            raise LinkedInJobsScraperError(
                "Bright Data LinkedIn Jobs scrape did not finish synchronously "
                f"(HTTP 202).{detail}"
            )

        if response.status_code >= 400:
            detail = (response.text or "").strip()[:500]
            raise LinkedInJobsScraperError(
                f"Bright Data LinkedIn Jobs returned HTTP {response.status_code}: {detail}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise LinkedInJobsScraperError(
                "Bright Data LinkedIn Jobs returned non-JSON response."
            ) from exc

        items = self._as_items(payload)
        if not items:
            raise LinkedInJobsScraperError(
                f"Bright Data LinkedIn Jobs returned no results for URL: {job_url}"
            )

        first = items[0]
        if not isinstance(first, dict):
            raise LinkedInJobsScraperError(
                "Bright Data LinkedIn Jobs returned an unexpected item shape."
            )

        if first.get("error") or first.get("error_code"):
            err = first.get("error") or first.get("error_code")
            raise LinkedInJobsScraperError(
                f"Bright Data LinkedIn Jobs scrape error for URL {job_url}: {err}"
            )

        try:
            return map_brightdata_item_to_job_posting(
                first, url=job_url, source="linkedin"
            )
        except ValueError as exc:
            raise LinkedInJobsScraperError(str(exc)) from exc

    @staticmethod
    def _as_items(payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return data
            items = payload.get("items")
            if isinstance(items, list):
                return items
            # Single record object
            if "job_summary" in payload or "url" in payload:
                return [payload]
        return []
