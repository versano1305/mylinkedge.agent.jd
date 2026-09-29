# JD extract persistence (Supabase)

## Schema mapping (`public.job_description`)

| Column | Use |
|--------|-----|
| `id` | UUID PK; graph input `jd_id` |
| `company_name` | Display name; set on `copy_paste` create, else filled by fetch/extract |
| `title_name` | Job title; same lifecycle as `company_name` |
| `origin_jd` | Raw pasted JD text **or** job posting URL (audit source) |
| `origin_type` | Source kind (`copy_paste`, `linkedin_url`, …); drives graph routing |
| `origin_id` | Dedupe key set at row creation; **not** read/written by the extraction graph |
| `skills` | Extracted skills jsonb |
| `extraction_status` | `pending` → `extracting` → `done` / `failed` |
| `company_id` | Resolved company record id |
| `sections` | Structured JD sections jsonb: `title`, plus `canonical` (the full parse). Flat `description` / `requirements` / `responsibilities` / `location` are not stored; project them with `legacy_sections` |
| `last_updated` | Touched on every agent write |

**Dropped (legacy):** `data` (base64 text), `origin`, `company`, `title`.

Migration notes (fullstack):

- Greenfield: `apps/candidate/supabase/migrations/202609140001_job_description.sql`
- Drop legacy `data` (idempotent): `202609160001_job_description_drop_data.sql`

RLS: authenticated SELECT / INSERT / **UPDATE** with `using (true)` (shared catalog).

## Prompt config (`public.agent_prompt_config`)

Migration `202609150001_agent_prompt_config.sql` in `mylinkedge.fullstack`.

| Column | Use |
|--------|-----|
| `type` | Process grouping key (e.g. `jd_section_extraction`) |
| `key` | Record key within the type; for section rows this is also `section_type` |
| `data` | jsonb payload (headings, templates, rules, `legacy_target`, …) |
| `sort_order` | Emission / display order |
| `enabled` | Soft disable without delete |

Seeded for `jd_section_extraction`: five section rows plus `system_prompt`, `parse_rules`, and `user_prompt`. The agent reads via `prompt_config_repository.list_by_type`; it does not write config at runtime.

RLS: authenticated SELECT.

## Auth (secret key)

The agent is a server-side runtime and authenticates with a Supabase **secret key** (`sb_secret_…`). That key maps to the `service_role` Postgres role and **bypasses RLS**. Never put it in a browser, mobile app, or source control.

Env:

- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY` — from Dashboard → Settings → API Keys (or the legacy `service_role` JWT while migrating)

See [Secret keys and elevated access](https://supabase.com/docs/guides/getting-started/api-keys#secret-keys-and-elevated-access).

Fullstack creates the JD row first, then invokes with `jd_id` only:

```python
await graph.ainvoke({"jd_id": "..."})
```

Client factory: `jd_agent.integrations.supabase.create_supabase_client` / `client_from_env`.

## Failure status

On any uncaught graph error, the invoke wrapper should call:

```python
from jd_agent.integrations.supabase import client_from_env, mark_failed

try:
    await graph.ainvoke({"jd_id": jd_id})
except Exception:
    mark_failed(client_from_env(), jd_id)
    raise
```

## Fullstack handoff (candidate app)

Ensure the agent runtime has `SUPABASE_SECRET_KEY` set. Create the `job_description` row (`origin_jd`, `origin_type`, `origin_id`, …), then invoke the agent with `jd_id` only.

Types / repos: `JobDescription` uses `company_name`, `title_name`, `origin_jd`, `origin_type`, `origin_id` (no `data` column).
