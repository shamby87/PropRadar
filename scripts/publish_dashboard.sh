#!/usr/bin/env bash
# Regenerate the PropRadar dashboard data and publish it to GitHub Pages.
#
# Reads the live Google Sheets via src.dashboard.export, writes
# docs/data/stats.json, then commits and pushes only that file.
#
# One-time setup (GitHub web UI): Settings -> Pages -> Build and deployment ->
# Source: "Deploy from a branch" -> Branch: main, Folder: /docs.
#
# Usage:  ./scripts/publish_dashboard.sh ["optional commit message"]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

DATA_FILE="docs/data/stats.json"
MSG="${1:-chore(dashboard): refresh performance data}"

echo "Exporting dashboard data..."
"$PYTHON" -m src.dashboard.export

if git diff --quiet -- "$DATA_FILE"; then
  echo "No changes in $DATA_FILE; nothing to publish."
  exit 0
fi

echo "Publishing $DATA_FILE..."
git add "$DATA_FILE"
git commit -m "$MSG"
git push

echo "Done. GitHub Pages will redeploy shortly."
