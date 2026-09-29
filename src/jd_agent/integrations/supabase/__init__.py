"""Supabase integration package for JD persistence."""

from jd_agent.integrations.supabase.client import (
    SupabaseSettings,
    client_from_env,
    create_supabase_client,
)
from jd_agent.integrations.supabase.jd_repository import (
    JOB_DESCRIPTION_TABLE,
    URL_ORIGIN_TYPES,
    JobDescription,
    JobDescriptionExtractionStatus,
    JobDescriptionOriginType,
    JobDescriptionSkill,
    get_by_id,
    get_sections,
    mark_failed,
    update_company,
    update_extraction_status,
    update_names,
    upsert_sections,
    upsert_skills,
)
from jd_agent.integrations.supabase.prompt_config_repository import (
    AGENT_PROMPT_CONFIG_TABLE,
    JD_SECTION_EXTRACTION,
    PROCESS_META_KEYS,
    PromptConfigRow,
    get_row_by_key,
    list_by_type,
    section_rows,
)

__all__ = [
    "AGENT_PROMPT_CONFIG_TABLE",
    "JD_SECTION_EXTRACTION",
    "JOB_DESCRIPTION_TABLE",
    "URL_ORIGIN_TYPES",
    "JobDescription",
    "JobDescriptionExtractionStatus",
    "JobDescriptionOriginType",
    "JobDescriptionSkill",
    "PROCESS_META_KEYS",
    "PromptConfigRow",
    "SupabaseSettings",
    "client_from_env",
    "create_supabase_client",
    "get_by_id",
    "get_row_by_key",
    "get_sections",
    "list_by_type",
    "mark_failed",
    "section_rows",
    "update_company",
    "update_extraction_status",
    "update_names",
    "upsert_sections",
    "upsert_skills",
]
