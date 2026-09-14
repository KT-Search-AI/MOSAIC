#!/usr/bin/env bash
# MOSAIC API - curl examples
#   ./examples.sh      (public endpoint + demo account; override with MOSAIC_BASE_URL /
#                       MOSAIC_USERNAME / MOSAIC_PASSWORD)
set -euo pipefail

BASE="${MOSAIC_BASE_URL:-https://app-d40d64a2.proxy1.ainexus.ktcloud.com}"
USER="${MOSAIC_USERNAME:-demo}"
PASS="${MOSAIC_PASSWORD:-ktmosaic}"
JAR=$(mktemp)
trap 'rm -f "$JAR"' EXIT

echo "== 0. health check =="
curl -s "$BASE/api/version"; echo

echo "== 1. login (stores session cookie) =="
curl -s -c "$JAR" -X POST "$BASE/api/mosaic/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}"; echo

echo "== 2. ask against the pre-built medical knowledge base =="
curl -s -b "$JAR" -X POST "$BASE/api/mosaic/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "database": "medical",
    "question": "What is the most common type of skin cancer?",
    "domain": "medical",
    "question_type": "Fact Retrieval"
  }' | head -c 1200; echo

echo "== 3. ask against the pre-built novel knowledge base =="
curl -s -b "$JAR" -X POST "$BASE/api/mosaic/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "database": "novel",
    "question": "Summarize the relationship between King Arthur and Launcelot.",
    "domain": "novel",
    "question_type": "Contextual Summarize"
  }' | head -c 1200; echo
