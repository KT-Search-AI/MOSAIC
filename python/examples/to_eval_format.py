"""Convert reproduce_benchmark.py output into the official GraphRAG-Bench
evaluation input.

The official scorers (Evaluation/generation_eval.py and
Evaluation/retrieval_eval.py in github.com/GraphRAG-Bench/GraphRAG-Benchmark)
read a JSON list of records shaped like the output of their Examples/run_*.py:

    {"id", "question", "source", "question_type", "context", "evidence",
     "generated_answer", "ground_truth"}

`ground_truth` and `evidence` come from the official question file;
`generated_answer` and `context` (the retrieved passage texts) come from the
API answers. If an id was retried, its last successful row is used.

    python to_eval_format.py medical_answers.jsonl medical_questions.json \
        --out medical_eval_input.json
"""

import argparse
import json
import sys
from pathlib import Path


def load_answers(path: Path) -> dict:
    answers = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "error" not in row:
            answers[str(row["id"])] = row  # later rows win
    return answers


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("answers", help="JSONL written by reproduce_benchmark.py")
    parser.add_argument("questions", help="official GraphRAG-Bench question file (JSON)")
    parser.add_argument("--out", required=True, help="output JSON for the official scorers")
    args = parser.parse_args()

    answers = load_answers(Path(args.answers))
    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))

    records, missing = [], []
    for q in questions:
        row = answers.get(str(q["id"]))
        if row is None:
            missing.append(str(q["id"]))
            continue
        records.append({
            "id": q["id"],
            "question": q["question"],
            "source": q.get("source", ""),
            "question_type": q["question_type"],
            "context": [doc["content"] for doc in row.get("retrieved_documents", [])],
            "evidence": q.get("evidence", ""),
            "generated_answer": row["answer"],
            "ground_truth": q.get("answer", ""),
        })

    Path(args.out).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(records)} / {len(questions)} records -> {args.out}")
    if missing:
        print(f"WARNING: {len(missing)} question(s) have no successful answer "
              f"(e.g. {', '.join(missing[:5])}). Re-run reproduce_benchmark.py with the "
              "same --out to retry them, then convert again.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
