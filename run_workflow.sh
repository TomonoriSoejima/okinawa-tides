#!/usr/bin/env bash
set -e

echo "Triggering workflow..."
gh workflow run scrape.yml
sleep 8

RUN_ID=$(gh run list --workflow=scrape.yml --limit=1 --json databaseId --jq '.[0].databaseId')
echo "Run ID: $RUN_ID"

gh run watch "$RUN_ID" --exit-status
