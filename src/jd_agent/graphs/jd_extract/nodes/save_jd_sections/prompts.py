"""Prompt builders for JD section partitioning (config-driven)."""

from __future__ import annotations

from jd_agent.graphs.jd_extract.nodes.save_jd_sections.models import (
    SectionConfig,
    section_config_from_row,
)
from jd_agent.integrations.supabase.prompt_config_repository import (
    PromptConfigRow,
    get_row_by_key,
    section_rows,
)


def section_configs_from_rows(rows: list[PromptConfigRow]) -> list[SectionConfig]:
    """Parse section partition rows into ``SectionConfig`` view models."""
    configs: list[SectionConfig] = []
    for row in section_rows(rows):
        configs.append(
            section_config_from_row(
                key=row.key,
                data=row.data if isinstance(row.data, dict) else {},
                sort_order=row.sort_order,
            )
        )
    return configs


def format_section_definitions_for_prompt(
    section_configs: list[SectionConfig],
) -> str:
    """Render the section-partition spec the LLM must follow."""
    lines: list[str] = []
    for entry in section_configs:
        lines.append(f"  section_type={entry.key!r}")
        lines.append(f"    heading: {entry.heading}")
        lines.append(f"    typical content: {entry.typical_content}")
        lines.append(f"    move here: {entry.section_description}")
        lines.append("")
    return "\n".join(lines)


def _format_rules(rules: list[str]) -> str:
    return "\n".join(f"- {rule}" for rule in rules if str(rule).strip())


def build_system_prompt(config_rows: list[PromptConfigRow]) -> str:
    """Interpolate ``{section_definitions}`` and ``{rules}`` into the system template."""
    system_row = get_row_by_key(config_rows, "system_prompt")
    if system_row is None:
        raise ValueError("agent_prompt_config missing system_prompt for process")

    template = str((system_row.data or {}).get("template") or "").strip()
    if not template:
        raise ValueError("system_prompt template is empty")

    rules_row = get_row_by_key(config_rows, "parse_rules")
    raw_rules = (rules_row.data or {}).get("rules") if rules_row else None
    rules_list = [str(r) for r in raw_rules] if isinstance(raw_rules, list) else []

    section_configs = section_configs_from_rows(config_rows)
    if not section_configs:
        raise ValueError("agent_prompt_config has no section partition rows")

    return template.format(
        section_definitions=format_section_definitions_for_prompt(section_configs),
        rules=_format_rules(rules_list),
    )


def build_user_message(jd_text: str, config_rows: list[PromptConfigRow]) -> str:
    """Interpolate ``{jd_text}`` into the user_prompt template."""
    body = (jd_text or "").strip()
    if not body:
        raise ValueError("jd_text is empty")

    user_row = get_row_by_key(config_rows, "user_prompt")
    if user_row is None:
        raise ValueError("agent_prompt_config missing user_prompt for process")

    template = str((user_row.data or {}).get("template") or "").strip()
    if not template:
        raise ValueError("user_prompt template is empty")

    return template.format(jd_text=body)
