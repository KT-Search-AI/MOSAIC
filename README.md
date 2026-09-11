# MOSAIC Public SDK

Public REST API access to **MOSAIC** — KT's graph-based retrieval-augmented
generation system, evaluated on
[GraphRAG-Bench](https://arxiv.org/abs/2506.05690) (medical / novel corpora).

- **Endpoint**: `https://api.mosaic.example.com` <!-- TODO: real endpoint -->
- **OpenAPI spec**: [`openapi.yaml`](openapi.yaml)
- **Access**: call `/api/mosaic/login` first; all `/api/mosaic/*` routes
  require the session cookie. Credentials are issued to benchmark reviewers.

The API exposes the **exact retrieval + answering pipeline used for the
benchmark submission** against pre-built knowledge bases. No scoring endpoints
are provided — evaluation should be performed with the official
GraphRAG-Bench scripts (separation of player and referee).

## Pre-built knowledge bases

| `database` | corpus |
|---|---|
| `medical` | GraphRAG-Bench medical |
| `novel` | GraphRAG-Bench novel |

## API overview

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/version` | GET | service version / health check (no auth) |
| `/api/mosaic/login` | POST | exchange credentials for the session cookie |
| `/api/mosaic/answer` | POST | retrieval-augmented question answering |

All JSON responses (except `/api/version`) use the envelope
`{"code": 0, "message": "ok", "payload": {...}}`; non-zero `code` is an error.

### `answer` request

| field | type | values |
|---|---|---|
| `database` | str | `medical`, `novel` |
| `question` | str | natural-language question |
| `domain` | str | `medical` / `novel` / `generic` (default `medical`) |
| `question_type` | str | `Fact Retrieval` / `Complex Reasoning` / `Contextual Summarize` / `Creative Generation` |
| `top_k` | int | number of retrieved documents (default 10) |
| `query_id` | str, optional | caller-side id, echoed back |

### `answer` response payload

```json
{
  "answer": "...generated answer...",
  "retrieval": {
    "backend": "mosaic",
    "documents": [
      {"uid": "document id", "rank": 1, "score": 0.83, "content": "..."}
    ]
  },
  "answering": {
    "domain": "medical",
    "question_type": "Fact Retrieval",
    "query_id": null,
    "model": "..."
  }
}
```

## Quickstart (Python ≥ 3.8, zero dependencies)

```bash
export MOSAIC_BASE_URL=https://api.mosaic.example.com
export MOSAIC_USERNAME=demo
export MOSAIC_PASSWORD=...
cd python
python examples/quickstart.py
```

```python
from mosaic_client import MosaicClient

client = MosaicClient("https://api.mosaic.example.com")
client.login("demo", "...")          # or: client = MosaicClient.from_env()

result = client.answer(
    database="medical",
    question="What is the most common type of skin cancer?",
    domain="medical",
    question_type="Fact Retrieval",
    top_k=10,
)
print(result["answer"])
print(result["retrieval"]["documents"][0]["uid"])
```

The client keeps the session cookie, re-authenticates once on HTTP 401, and
retries transient failures (429 / 502 / 503 / 504 / network errors) with
exponential backoff. Errors raise `MosaicError` (with `.status` for HTTP
errors and `.code` for API envelope errors).

## Reproduce a benchmark run

```bash
# built-in 4-question sample (one per question type)
python examples/reproduce_benchmark.py

# full GraphRAG-Bench question file (from the official Datasets release)
python examples/reproduce_benchmark.py medical_questions.json --out medical_answers.jsonl
python examples/reproduce_benchmark.py novel_questions.json --out novel_answers.jsonl --concurrency 4
```

Output is JSONL with one row per question containing `answer` and
`retrieved_documents`, consumable by retrieval-only (recall / context
relevancy) and end-to-end (generation) evaluation alike. Runs are resume-safe:
re-running skips ids that already succeeded and retries failed ones (when an
id appears more than once, use its last non-error row).

## curl

See [`curl/examples.sh`](curl/examples.sh) for the workflow with plain `curl`.

## Tests

```bash
cd python
python -m unittest discover -s tests -v
```

The tests run against a local mock server implementing `openapi.yaml`, so
they need no network access.
