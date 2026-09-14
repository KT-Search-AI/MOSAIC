"""Quickstart: ask questions against the pre-built benchmark knowledge bases.

The service ships with two pre-built knowledge bases covering the
GraphRAG-Bench corpora:

    medical  - GraphRAG-Bench medical corpus
    novel    - GraphRAG-Bench novel corpus

Run:
    export MOSAIC_BASE_URL=https://<mosaic-api-host>
    export MOSAIC_USERNAME=demo
    export MOSAIC_PASSWORD=<password>
    python quickstart.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mosaic_client import MosaicClient

QUESTIONS = [
    {
        "database": "medical",
        "domain": "medical",
        "question_type": "Fact Retrieval",
        "question": "What is the most common type of skin cancer?",
    },
    {
        "database": "medical",
        "domain": "medical",
        "question_type": "Complex Reasoning",
        "question": (
            "Why is a patient with fair skin and a history of organ transplant "
            "at particularly high risk for developing basal cell carcinoma?"
        ),
    },
    {
        "database": "novel",
        "domain": "novel",
        "question_type": "Contextual Summarize",
        "question": (
            "Summarize the relationship between King Arthur and Launcelot "
            "based on the retrieved passages."
        ),
    },
]


def main() -> None:
    if not (os.environ.get("MOSAIC_USERNAME") and os.environ.get("MOSAIC_PASSWORD")):
        sys.exit("set MOSAIC_USERNAME and MOSAIC_PASSWORD (and MOSAIC_BASE_URL)")

    client = MosaicClient.from_env()
    print("endpoint:", client.base_url)
    print("service version:", client.version().get("version"))

    for item in QUESTIONS:
        print("=" * 78)
        print(f"[{item['database']} / {item['question_type']}]")
        print("Q:", item["question"])
        result = client.answer(
            item["database"],
            item["question"],
            domain=item["domain"],
            question_type=item["question_type"],
        )
        print("A:", result["answer"])
        documents = result["retrieval"]["documents"]
        print(f"retrieved {len(documents)} documents:")
        for doc in documents[:3]:
            print(f"   #{doc['rank']} {doc['uid']} (score={doc['score']:.3f})")


if __name__ == "__main__":
    main()
