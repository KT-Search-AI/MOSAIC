"""Reproduce a GraphRAG-Bench evaluation run through the MOSAIC public API.

Two modes:

  1. Built-in sample (no files needed):
         python reproduce_benchmark.py

  2. Full question file from the GraphRAG-Bench release
     (Datasets/Questions/medical_questions.json or novel_questions.json):
         python reproduce_benchmark.py medical_questions.json --out results.jsonl

Each answer call returns both the generated answer and the top-k retrieved
documents, so retrieval-only or end-to-end metrics can be computed from the
same output file. Runs are resume-safe: ids already present in ``--out``
without an error are skipped.

Credentials come from MOSAIC_BASE_URL / MOSAIC_USERNAME / MOSAIC_PASSWORD.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mosaic_client import MosaicClient

SAMPLE_QUESTIONS = [
    {"id": "sample-fr", "question_type": "Fact Retrieval",
     "question": "What is the most common type of skin cancer?"},
    {"id": "sample-cr", "question_type": "Complex Reasoning",
     "question": "Why is a patient with fair skin and a history of organ transplant at particularly high risk for developing basal cell carcinoma?"},
    {"id": "sample-cs", "question_type": "Contextual Summarize",
     "question": "What are the main risk factors associated with the development of basal cell carcinoma?"},
    {"id": "sample-cg", "question_type": "Creative Generation",
     "question": "Write a short consult note for a patient referred for evaluation of a suspicious lesion on the face."},
]


def load_questions(path, database, domain):
    if not path:
        rows = [dict(row) for row in SAMPLE_QUESTIONS]
        inferred = "medical"
    else:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
        inferred = "novel" if "novel" in Path(path).name.lower() else "medical"
    database = database or inferred
    domain = domain or (database if database in ("medical", "novel") else "generic")
    for row in rows:
        row["database"] = database
        row["domain"] = domain
        row["id"] = str(row["id"])
    return rows


def load_done(out_path: Path) -> set:
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if "error" not in record:
                    done.add(str(record["id"]))
    return done


def run_one(client: MosaicClient, item: dict, top_k: int) -> dict:
    started = time.time()
    try:
        result = client.answer(
            item["database"],
            item["question"],
            domain=item["domain"],
            question_type=item.get("question_type", "Fact Retrieval"),
            top_k=top_k,
            query_id=item["id"],
        )
        return {
            "id": item["id"],
            "question_type": item.get("question_type"),
            "question": item["question"],
            "answer": result["answer"],
            "retrieved_documents": result["retrieval"]["documents"],
            "elapsed_s": round(time.time() - started, 1),
        }
    except Exception as error:  # noqa: BLE001 - keep batch running
        return {"id": item["id"], "error": str(error)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("questions", nargs="?", default=None,
                        help="optional path to a GraphRAG-Bench questions JSON file")
    parser.add_argument("--out", default="api_answers.jsonl",
                        help="output JSONL path (one row per question)")
    parser.add_argument("--database", default=None,
                        help="knowledge base (default: inferred from file name)")
    parser.add_argument("--domain", default=None,
                        help="medical | novel | generic (default: follows database)")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=1,
                        help="parallel requests (keep low to respect rate limits)")
    args = parser.parse_args()

    if not (os.environ.get("MOSAIC_USERNAME") and os.environ.get("MOSAIC_PASSWORD")):
        sys.exit("set MOSAIC_USERNAME and MOSAIC_PASSWORD (and MOSAIC_BASE_URL)")

    questions = load_questions(args.questions, args.database, args.domain)
    client = MosaicClient.from_env()

    out_path = Path(args.out)
    done = load_done(out_path)
    remaining = [q for q in questions if q["id"] not in done]
    print(f"questions: {len(questions)} total, {len(remaining)} to run (resume-safe)")

    failures = 0
    with out_path.open("a", encoding="utf-8") as out, \
            ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [pool.submit(run_one, client, item, args.top_k) for item in remaining]
        for index, future in enumerate(as_completed(futures), start=1):
            record = future.result()
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            ok = "error" not in record
            failures += not ok
            print(f"[{index}/{len(remaining)}] {'OK' if ok else 'FAIL'} {record['id']} "
                  f"({record.get('elapsed_s', '?')}s)"
                  + ("" if ok else f" - {record['error'][:200]}"))

    print(f"saved -> {out_path} ({failures} failed; re-run to retry them)")


if __name__ == "__main__":
    main()
