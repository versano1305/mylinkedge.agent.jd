# JD Extract Graph Plan

## Topic 1: Input Preparation And Initial Persistence

### Agreed Decisions

- The graph accepts Studio / API input through `JdExtractState` with **`jd_id` only**.
- Fullstack creates the `job_description` row before invoke, setting `origin_jd`, `origin_type`, `origin_id`, and (for `copy_paste`) `company_name` / `title_name`.
- `load_jd` hydrates graph state from the DB; source fields are not duplicated as invoke inputs.
- Supported `origin_type` values include `copy_paste` and URL types (`linkedin_url`, …).
- For URL origins, the graph invokes an external retrieval service (`fetch_jd`) using `origin_jd` as the URL.
- For `copy_paste`, `prepare_jd_text` uses `origin_jd` as the plain-text JD body.
- Skills are extracted only in a later phase of the graph.
- Company may come from paste input, URL retrieval, or a later agent.
- `company_id` means an existing company database record ID.
- The graph updates the existing JD record and its sections instead of creating a new JD record.

### Initial Structured JD Fields (DB)

- `origin_jd` / `origin_type` — set at create time.
- `title_name`, `company_name` — set on paste; empty for URL until fetch/extract.
- `sections` — written by `save_jd_sections`.
- `skills`, `company_id` — written by `upsert_extraction`.

## Topic 2: State Shape

### Agreed Decisions

- `JdExtractState` keeps explicit, minimal fields.
- `jd_id` is required; `jd: JobDescription` is loaded by `load_jd`.
- Skills live inside `extraction`, not as a separate top-level state field.
- Extraction status is mirrored in graph state and DB as ``extraction_status``.

### State Fields

- `jd_id`: required ID of the JD record being processed.
- `jd`: loaded `JobDescription` row (origin_jd, origin_type, company_name, title_name, …).
- `jd_text`: normalized plain-text JD after fetch or copy-paste.
- `jd_sections`: optional in-memory parse dump after `save_jd_sections`.
- `company_id`: resolved existing company database record ID.
- `extraction`: extracted information, including skills.
- `extraction_status`: `extracting` → `done` / `failed`.

**Removed from state:** `content`, `type`, `source`, `user_id`, `company_name`, `title`, `source_url`, `errors`.

## Topic 3: Graph Skeleton And Routing

### Agreed Decisions

- `fetch_jd` remains a separate optional node.
- Structuring always works on normalized `jd_text`.
- Conditional routing uses `jd.origin_type` (`route_by_origin_type`).
- Agent extraction runs before company resolution.
- `company_name` is guaranteed after agent extraction (paste, fetch, or agent).
- `resolve_company` runs after agent extraction.

### Flow

1. `load_jd` — SELECT by `jd_id`; validate `origin_jd` / `origin_type`.
2. Set JD extraction status to extracting.
3. Route by `origin_type`.
4. For URL types, run `fetch_jd`.
5. Normalize into `jd_text`.
6. Structure JD text into saved sections on `jd_id`.
7. Run extraction agents.
8. Resolve `jd.company_name` to an existing `company_id`.
9. Upsert extracted results, including `company_id`.
10. Set JD record status to done.

## Topic 4: Agent Extraction Structure

### Agreed Decisions

- Start with one extraction node.
- The extraction node loads JD data from the database using `jd_id`.
- Extraction results are written to graph state first.
- A final `upsert_extraction` node writes extracted results back to the database.
- If required extraction data is missing or low confidence, the graph should fail instead of completing with partial results.

### Current Skeleton Direction

1. `extract_jd_info` loads the saved JD sections from the database by `jd_id`.
2. `extract_jd_info` invokes one agent to extract the required information.
3. The result is stored in `extraction` (and may patch `jd.company_name` / `jd.title_name`).
4. `resolve_company` uses the extracted or provided `company_name`.
5. `upsert_extraction` persists the final extraction result and resolved `company_id`.

## Topic 5: Failure And Status Contract

### Agreed Decisions

- On failure, the graph should both update the JD database status and raise an exception.
- Nodes should raise exceptions immediately.
- Required success fields are `company_id` and `skills`.
- If `resolve_company` cannot resolve an existing company ID, the graph should fail.
- Supported extraction statuses are `extracting`, `done`, and `failed` (plus DB `pending` before invoke).

## Topic 6: Implementation Interfaces And Mocks

### Mocked Boundaries

- External JD retrieval tool.
- Company resolution tool.
- ~~JD section persistence/update operations.~~ → Supabase `job_description` via secret key (`SUPABASE_SECRET_KEY`).
- ~~Extraction result upsert.~~ → same repository (`skills`, `company_id`).
- ~~Extraction status updates.~~ → `extraction_status` column.

LLM extraction and company resolution remain mocked / placeholder until wired.
