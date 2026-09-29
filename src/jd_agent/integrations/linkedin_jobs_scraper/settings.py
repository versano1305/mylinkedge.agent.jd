"""Configuration for Bright Data LinkedIn Jobs scraper (collect by URL)."""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_BASE_URL = "https://api.brightdata.com"
_DEFAULT_DATASET_ID = "gd_lpfll7v5hcqtkxl6l"
_DEFAULT_TIMEOUT_SECONDS = 90.0


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class LinkedInJobsScraperSettings:
    """Settings for Bright Data LinkedIn job listings (collect by URL).

    Environment keys:

    - ``BRIGHTDATA_API_TOKEN`` — required Bright Data API token
    - ``BRIGHTDATA_BASE_URL`` — API base (default ``https://api.brightdata.com``)
    - ``BRIGHTDATA_LINKEDIN_JOBS_DATASET_ID`` — dataset id
      (default ``gd_lpfll7v5hcqtkxl6l``)
    - ``BRIGHTDATA_TIMEOUT_SECONDS`` — HTTP timeout (default ``90``)
    """

    api_token: str
    base_url: str = _DEFAULT_BASE_URL
    dataset_id: str = _DEFAULT_DATASET_ID
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> LinkedInJobsScraperSettings:
        return cls(
            api_token=os.getenv("BRIGHTDATA_API_TOKEN", "").strip(),
            base_url=os.getenv("BRIGHTDATA_BASE_URL", "").strip() or _DEFAULT_BASE_URL,
            dataset_id=(
                os.getenv("BRIGHTDATA_LINKEDIN_JOBS_DATASET_ID", "").strip()
                or _DEFAULT_DATASET_ID
            ),
            timeout_seconds=_env_float(
                "BRIGHTDATA_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS
            ),
        )
