"""Tools used by the JD extraction graph."""

from __future__ import annotations

from langchain_core.tools import tool

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
def fetch_job_posting(url: str, source: str = "linkedin") -> JobPosting:
    """Fetch a structured job posting from a job-board URL.

    Returns a generic ``JobPosting`` (description, title, company_name, …)
    independent of the underlying retrieval API.
    """
    return fetch_job_posting_impl(url, source)


# Fixed ID returned by the mock company-resolution tool.
_MOCK_COMPANY_ID = "company_mock_0001"


@tool
def resolve_company_id(company_name: str) -> str:
    """Resolve a company name to an existing company DB record ID.

    Mocked for now: returns a fixed existing ``company_id`` regardless of input.

    TODO: replace the mock with a real lookup against the company data layer.
    Search existing companies by ``company_name`` (and any provenance hints),
    return the matching ``company_id``, and raise a domain error when no
    existing company can be resolved so the graph fails per the plan.
    """
    if not company_name:
        raise ValueError("company_name is required to resolve a company_id")
    return _MOCK_COMPANY_ID
