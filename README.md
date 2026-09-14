# MOSAIC Public SDK

Public REST API access to **MOSAIC** — KT's graph-based retrieval-augmented
generation system, evaluated on
[GraphRAG-Bench](https://arxiv.org/abs/2506.05690) (medical / novel corpora).

- **Technical report**: [MOSAIC: Query-Aware Exploration Policy Adaptation for
  GraphRAG](https://arxiv.org/abs/2609.11065) (arXiv:2609.11065)
- **Release date**: 2026-09-10
- **Endpoint**: `https://app-d40d64a2.proxy1.ainexus.ktcloud.com`
- **OpenAPI spec**: [`openapi.yaml`](openapi.yaml) · interactive docs at
  [`/docs`](https://app-d40d64a2.proxy1.ainexus.ktcloud.com/docs)
- **Access**: username `demo` / password `ktmosaic` (call `/api/mosaic/login`
  first; all `/api/mosaic/*` routes require the session cookie)

The API exposes the **exact retrieval + answering pipeline used for the
benchmark submission** against pre-built knowledge bases. No scoring endpoints
are provided — evaluation should be performed with the official
GraphRAG-Bench scripts (separation of player and referee).

## Evaluation setup

| | |
|---|---|
| Generation model | `gpt-4o-mini`, temperature 0 |
| Evaluation judge | `gpt-4o-mini`, temperature 0 |
| Embedding model (evaluation) | `BAAI/bge-large-en-v1.5` |
| Questions | all questions of both subsets: Medical 2,062 / Novel 2,010 |

Metrics per question type follow GraphRAG-Bench: ROUGE-L and answer
correctness (Fact Retrieval, Complex Reasoning), answer correctness and
coverage (Contextual Summarize), and answer correctness, coverage and
faithfulness (Creative Generation).

## Pre-built knowledge bases

| `database` | corpus |
|---|---|
| `medical` | GraphRAG-Bench medical |
| `novel` | GraphRAG-Bench novel |

## API overview

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/version` | GET | service version + knowledge-base load state (no auth) |
| `/api/mosaic/login` | POST | exchange credentials for the session cookie |
| `/api/mosaic/answer` | POST | retrieval-augmented question answering |

All JSON responses (except `/api/version`) use the envelope
`{"code": 0, "message": "ok", "payload": {...}}`; non-zero `code` is an error.

| situation | response |
|---|---|
| success | HTTP 200, `code: 0` |
| bad credentials | HTTP 200, `code: 40101` |
| unknown `database` | HTTP 200, `code: 40401` |
| answer generation failed | HTTP 200, `code: 50001` (retry later) |
| missing / expired session | HTTP 401 (the client re-logs in once) |
| invalid request | HTTP 422 |
| too many requests in flight | HTTP 429 (the client retries with backoff) |
| knowledge base loading | HTTP 503 (the client retries with backoff) |

### `answer` request

| field | type | values |
|---|---|---|
| `database` | str | `medical`, `novel` |
| `question` | str | natural-language question |
| `domain` | str | `medical` / `novel` / `generic` (default `medical`) |
| `question_type` | str | `Fact Retrieval` / `Complex Reasoning` / `Contextual Summarize` / `Creative Generation` |
| `query_id` | str, optional | caller-side id, echoed back |

Every answer is produced with the benchmark-submission configuration:
retrieval breadth and depth are chosen per question by MOSAIC's query analyzer,
and the answer is grounded on **15 source passages** reranked from the graph
evidence. There is no caller-side retrieval-size knob.

### `answer` response payload

```json
{
  "answer": "...generated answer...",
  "retrieval": {
    "backend": "mosaic",
    "documents": [
      {"uid": "chunk-9b42…:800", "rank": 1, "score": 0.83, "content": "..."}
    ]
  },
  "answering": {
    "domain": "medical",
    "question_type": "Fact Retrieval",
    "query_id": null,
    "model": "gpt-4o-mini"
  }
}
```

`documents` are exactly the passages shown to the answer model, in rank order.
`uid` is `<chunk_id>:<char_offset>`: a window of the source-corpus chunk
`chunk_id` starting at character `char_offset`. `score` is the reranker's
cosine similarity to the question.

## Quickstart (Python ≥ 3.8, zero dependencies)

```bash
cd python
python examples/quickstart.py
```

The examples use the public endpoint and demo account by default; set
`MOSAIC_BASE_URL` / `MOSAIC_USERNAME` / `MOSAIC_PASSWORD` to override.

```python
from mosaic_client import MosaicClient

client = MosaicClient("https://app-d40d64a2.proxy1.ainexus.ktcloud.com")
client.login("demo", "ktmosaic")     # or: client = MosaicClient.from_env()

result = client.answer(
    database="medical",
    question="What is the most common type of skin cancer?",
    domain="medical",
    question_type="Fact Retrieval",
)
print(result["answer"])
print(result["retrieval"]["documents"][0]["uid"])
```

The client keeps the session cookie, re-authenticates once on HTTP 401, and
retries transient failures (429 / 502 / 503 / 504 / network errors) with
exponential backoff. Errors raise `MosaicError` (with `.status` for HTTP
errors and `.code` for API envelope errors).

If Python reports `CERTIFICATE_VERIFY_FAILED` (common with the python.org
installer on macOS), run `Install Certificates.command` from your Python
folder, or point Python at the certifi bundle:
`export SSL_CERT_FILE=$(python3 -m certifi)`.

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

## Citation

```bibtex
@article{lee2026mosaic,
  title   = {MOSAIC: Query-Aware Exploration Policy Adaptation for GraphRAG},
  author  = {Lee, EunKyeong and Oh, Kyeong-Jin and Kim, Jinwon and Lee, Hye Woo and
             Song, Minsang and Jang, Hyeongjun and Youn, Junyoung},
  journal = {arXiv preprint arXiv:2609.11065},
  year    = {2026}
}
```
