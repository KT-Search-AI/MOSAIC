#!/usr/bin/env bash
# MOSAIC API - curl examples
#   MOSAIC_BASE_URL=https://app-d40d64a2.proxy1.ainexus.ktcloud.com MOSAIC_USERNAME=demo MOSAIC_PASSWORD=... ./examples.sh
set -euo pipefail

BASE="${MOSAIC_BASE_URL:?set MOSAIC_BASE_URL}"
USER="${MOSAIC_USERNAME:?set MOSAIC_USERNAME}"
PASS="${MOSAIC_PASSWORD:?set MOSAIC_PASSWORD}"
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
