"""Tools used by the JD extraction graph."""

from __future__ import annotations

from langchain_core.tools import tool
from mylinkedge_agent_tools.langgraph_streaming.annotations import thinking

from jd_agent.integrations.linkedin_jobs_scraper import (
    LinkedInJobsScraperClient,
    is_linkedin_job_url,
)
from jd_agent.shared.schemas import JobPosting


def fetch_job_posting_impl(url: str, source: str = "linkedin") -> JobPosting:
    """Fetch a job posting from a job-board URL.

    Dispatches on ``source`` to a provider-specific client and always returns a
    vendor-agnostic ``JobPosting`` so the retrieval API can be swapped later.
    """
    job_url = (url or "").strip()
    if not job_url:
        raise ValueError("url is required to fetch a job posting")

    normalized_source = (source or "linkedin").strip().lower() or "linkedin"

    if normalized_source in {"linkedin", "generic"}:
        if not is_linkedin_job_url(job_url):
            raise ValueError(
                "linkedin fetch only supports LinkedIn job URLs "
                f"(got {job_url!r}). Pass type=raw/base64 for other sources."
            )
        with LinkedInJobsScraperClient() as client:
            return client.fetch_job_posting(job_url)

    raise ValueError(
        f"Unsupported job-board source {normalized_source!r}. "
        "Currently only 'linkedin' is supported."
    )


@tool
@thinking("Fetching job posting…")
def fetch_job_posting(url: str, source: str = "linkedin") -> JobPosting:
    """Fetch a structured job posting from a job-board URL.

    Returns a generic ``JobPosting`` (description, title, company_name, …)
    independent of the underlying retrieval API.
    """
    return fetch_job_posting_impl(url, source)
