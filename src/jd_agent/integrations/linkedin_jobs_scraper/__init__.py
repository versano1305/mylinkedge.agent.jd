"""Bright Data LinkedIn Jobs scraper integration (collect by URL)."""

from jd_agent.integrations.linkedin_jobs_scraper.client import (
    LinkedInJobsScraperClient,
    LinkedInJobsScraperError,
    is_linkedin_job_url,
)
from jd_agent.integrations.linkedin_jobs_scraper.mapper import (
    map_brightdata_item_to_job_posting,
)
from jd_agent.integrations.linkedin_jobs_scraper.settings import (
    LinkedInJobsScraperSettings,
)

__all__ = [
    "LinkedInJobsScraperClient",
    "LinkedInJobsScraperError",
    "LinkedInJobsScraperSettings",
    "is_linkedin_job_url",
    "map_brightdata_item_to_job_posting",
]
