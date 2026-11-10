# JD Agent

LangGraph project for job-description extraction. Graphs, nodes, and tools are skeletons with `TODO`s — fill them in as you implement each process.

## Graphs

| Graph | Role |
| --- | --- |
| `jd_extract` | Fetch or decode JD content, then parse into a structured extraction |
| `gap_collect` | Compute JD/user skill gaps and persist them on `user_resume_builder.gaps` |

Fit scores in `gap_collect` and `resume_generate` are normalized against Skill-ontology
growth; see [`docs/fit_normalization.md`](docs/fit_normalization.md).

Studio input for `gap_collect`:

```json
{
  "session_id": "user-resume-builder-uuid-here"
}
```

## Setup

`mylinkedge-agent-tools*` is installed from the sibling `../mylinkedge.agent.tools` checkout (editable paths in `pyproject.toml`). Everything else uses public PyPI. Restore the commented CodeArtifact sources in `pyproject.toml` before publish.

```bash
make install
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env` when you implement LLM nodes.

## Run Studio

```bash
make dev
```

Studio input example:

```json
{
  "content": "https://boards.greenhouse.io/example/jobs/123",
  "type": "url",
  "source": "greenhouse",
  "user_id": "candidate-uuid-here"
}
```

```json
{
  "content": "We are hiring a Senior Backend Engineer...",
  "type": "raw",
  "source": "paste",
  "user_id": "candidate-uuid-here"
}
```

## Container

The graphs can be hosted by a container runtime. SQS, HTTP (`/threads`), and gRPC are implemented.

`agent-jd-events` (LocalStack name `skills-ai-local-agent-jd-events`) delivers queued work only:

- `jd_extraction_queued` — invokes `jd_extract` with `payload.job_description_id`
- `jd_gap_analysis_queued` — invokes `gap_collect` with `payload.session_id`
- `resume_generate_queued` — invokes `resume_generate` with `payload.session_id`

Each graph publishes lifecycle start/end (and data where applicable), e.g.
``JD_EXTRACTION_START`` / ``JD_EXTRACTION_END`` for ``jd_extract``,
``JD_GAP_ANALYSIS_*`` for ``gap_collect``, ``RESUME_GENERATE_*`` for
``resume_generate``, via ``mylinkedge_agent_tools.event_hub``.
Set `JD_LIFECYCLE_EVENTS_ENABLED=0` to disable publishing.

Queue URLs and the dead-letter queue are in `skills.ai.ioc/localstack` (`stack-outputs.env` after deploy). Set `SQS_QUEUE_URL_PREFIX`, `SQS_QUEUE_NAME`, and `AWS_ENDPOINT_URL` (see `.env.example`), then:

```bash
make sqs-worker
```

### HTTP (`/threads`)

Gateway seeds threads with a service secret; browsers stream with a bearer session JWT
(see `interview copy.md`). Set `SERVICE_SECRET`, `SESSION_JWT_SECRET`, and Mongo
checkpointer vars from `.env.example`, then:

```bash
make http-server
```

`POST /threads` (header `X-Service-Secret`) — body examples:

```json
{ "graph_id": "jd_extract", "sub": "user:<uuid>", "context": { "jd_id": "<job-description-id>" } }
```

```json
{ "graph_id": "gap_collect", "sub": "user:<uuid>", "context": { "session_id": "<resume-builder-session-id>" } }
```

```json
{ "graph_id": "resume_generate", "sub": "user:<uuid>", "context": { "session_id": "<resume-builder-session-id>" } }
```

Response: `{ "thread_id", "graph_id", "sub" }`. Mint a session JWT in the gateway, then
`POST /threads/{thread_id}/stream` with `Authorization: Bearer …` for SSE `TurnEvent` frames.

### gRPC

```bash
make grpc-server
```

## Tests

```bash
make test
```

Live graph tests are skipped unless their opt-in flags are set (see `.env.example`):

```bash
# jd_extract (also needs LocalStack SNS utility topic + event hub consuming extract_skills)
RUN_JD_EXTRACT_INTEGRATION=1 JD_EXTRACT_TEST_JD_ID=... make test

# gap_collect (also needs NEO4J_* + a session whose JD is already extracted)
RUN_GAP_COLLECT_INTEGRATION=1 GAP_COLLECT_TEST_SESSION_ID=... make test

# resolve_company (LocalStack SNS + event hub status API + known Company.name)
RUN_RESOLVE_COMPANY_INTEGRATION=1 RESOLVE_COMPANY_TEST_COMPANY_NAME=Jifiti make test
```
