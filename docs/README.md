# KT-MOSAIC

This repository contains a compact reproduction package for the Medical and
Novel subsets of GraphRAG-Bench. KT-MOSAIC uses query-adaptive graph retrieval,
maps selected graph evidence back to source passages, reranks source windows
with BGE, and generates final answers from the selected passages.

## Overview

The goal of this package is to reproduce the answer-generation outputs for the
Medical and Novel subsets of GraphRAG-Bench using KT-MOSAIC. Instead of applying
one fixed retrieval configuration to all questions, the retrieval stage analyzes
each question and adjusts the graph search behavior before selecting evidence.
The selected graph evidence is then linked back to the original corpus passages
so that the answer model reads natural source text rather than only graph
triples.

The system runs in three stages:

1. Query-adaptive retrieval over the prebuilt graph store.
2. Source-window reranking with `BAAI/bge-large-en-v1.5`.
3. Answer generation with `gpt-4o-mini`.

The final exported JSON files are intended for external leaderboard evaluation
or API submission. Each output record includes the question, generated answer,
gold answer, evidence metadata, and the source-passage `context` that was
actually injected into the generation prompt. This keeps generation and
evaluation cleanly separated while preserving the exact context used by the
answer model.

## Setup

```bash
python -m pip install -r requirements.txt
export OPENAI_API_KEY=...
```

Required assets:

```text
data/medical_questions.json
data/novel_questions.json
data/rag_storage_medical.zip
data/rag_storage_novel.zip
models/BAAI_bge-large-en-v1.5
```

For the reported run, the embedding endpoint was served locally at
`http://127.0.0.1:8000/v1` with `bge-large-en-v1.5`.

## Run

```bash
bash run_generation.sh medical
bash run_generation.sh novel
```

The script reuses cached retrieval results when available and writes both the
raw generation run and the external-evaluation input JSON.

## Experimental Settings

| Setting | Value |
|---|---|
| Benchmark | GraphRAG-Bench Medical / Novel |
| Retrieval | query-adaptive graph retrieval |
| Reranker | `BAAI/bge-large-en-v1.5` bi-encoder |
| Rerank unit | sliding source window |
| Window size / stride | 1600 / 800 characters |
| Top-k windows | 15 |
| Answer model | `gpt-4o-mini` |

## Benchmark Results

The full result JSON is available at
[`benchmark_results.json`](benchmark_results.json).

The numbers below are from an internal generation-evaluation run.

| Dataset | **Overall** | Fact Retrieval | Complex Reasoning | Contextual Summarize | Creative Generation |
|---|---:|---:|---:|---:|---:|
| Medical | **0.7666** | 0.7586 | 0.7657 | 0.8546 | 0.6697 |
| Novel | **0.6433** | 0.6543 | 0.5757 | 0.7420 | 0.5664 |

## Code Structure

```text
run_generation.sh              # medical/novel generation entry point
run_pipeline.py                # retrieval entry point
pipeline_runtime.py            # shared runtime and API clients
scripts/run_retrieval.sh       # retrieval wrapper
scripts/run_generation.py      # source-window generation and JSON export
retriever/                     # graph retrieval and passage-window utilities
evaluation/                    # GraphRAG-Bench evaluation helpers
docs/benchmark_results.json    # reported benchmark results
```
