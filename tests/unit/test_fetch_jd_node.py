"""Unit tests for fetch_jd node LinkedIn URL handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from jd_agent.graphs.jd_extract.nodes import fetch_jd
from jd_agent.integrations.supabase.jd_repository import JobDescription
from jd_agent.shared.schemas import JobPosting


def test_fetch_jd_rejects_non_linkedin() -> None:
    with pytest.raises(ValueError, match="LinkedIn"):
        fetch_jd(
            {
                "jd": JobDescription(
                    id="1",
                    origin_type="linkedin_url",
                    origin_jd="https://boards.greenhouse.io/acme/jobs/1",
                ),
            }
        )


def test_fetch_jd_fills_jd_text_and_metadata() -> None:
    posting = JobPosting(
        url="https://www.linkedin.com/jobs/view/999",
        description="Full JD text",
        title="Senior Engineer",
        company_name="Acme Corp",
        location="Remote",
        source="linkedin",
    )
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.fetch_job_posting.return_value = posting

    with patch(
        "jd_agent.graphs.jd_extract.tools.LinkedInJobsScraperClient",
        return_value=mock_client,
    ):
        result = fetch_jd(
            {
                "jd": JobDescription(
                    id="1",
                    origin_type="linkedin_url",
                    origin_jd="https://www.linkedin.com/jobs/view/999",
                ),
            }
        )

    mock_client.fetch_job_posting.assert_called_once_with(
        "https://www.linkedin.com/jobs/view/999"
    )
    assert result["jd_text"] == "Full JD text"
    assert result["jd"].company_name == "Acme Corp"
    assert result["jd"].title_name == "Senior Engineer"


def test_fetch_jd_preserves_existing_company_and_title() -> None:
    posting = JobPosting(
        url="https://www.linkedin.com/jobs/view/999",
        description="Full JD text",
        title="Scraped Title",
        company_name="Scraped Co",
        source="linkedin",
    )
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.fetch_job_posting.return_value = posting

    with patch(
        "jd_agent.graphs.jd_extract.tools.LinkedInJobsScraperClient",
        return_value=mock_client,
    ):
        result = fetch_jd(
            {
                "jd": JobDescription(
                    id="1",
                    origin_type="linkedin_url",
                    origin_jd="https://www.linkedin.com/jobs/view/999",
                    company_name="Studio Co",
                    title_name="Studio Title",
                ),
            }
        )

    assert result == {"jd_text": "Full JD text"}
    assert "jd" not in result


def test_fetch_jd_rejects_unsupported_source() -> None:
    with pytest.raises(ValueError, match="Unsupported job-board source"):
        fetch_jd(
            {
                "jd": JobDescription(
                    id="1",
                    origin_type="greenhouse_url",
                    origin_jd="https://boards.greenhouse.io/acme/jobs/1",
                ),
            }
        )
