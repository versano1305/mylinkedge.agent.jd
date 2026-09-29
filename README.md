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

```bash
uv venv
source .venv/bin/activate
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

The graphs can be hosted by a container runtime. SQS is implemented; HTTP and gRPC are reserved.

`agent-jd-events` (LocalStack name `skills-ai-local-agent-jd-events`) delivers queued work only:

- `process.jd-extraction/queued` — invokes `jd_extract` with `job_description_id`
- `process.jd-gap-analysis/queued` — invokes `gap_collect` with `payload.session_id`
- `process.resume-generate/queued` — invokes `resume_generate` with `payload.session_id`

Queue URLs and the dead-letter queue are in `skills.ai.ioc/localstack` (`stack-outputs.env` after deploy). Set `SQS_QUEUE_URL_PREFIX`, `SQS_QUEUE_NAME`, and `AWS_ENDPOINT_URL` (see `.env.example`), then:

```bash
make sqs-worker
```

## Tests

```bash
make test
```

Live graph tests are skipped unless their opt-in flags are set (see `.env.example`):

```bash
# jd_extract
RUN_JD_EXTRACT_INTEGRATION=1 JD_EXTRACT_TEST_JD_ID=... make test

# gap_collect (also needs NEO4J_* + a session whose JD is already extracted)
RUN_GAP_COLLECT_INTEGRATION=1 GAP_COLLECT_TEST_SESSION_ID=... make test
```
