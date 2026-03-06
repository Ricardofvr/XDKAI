#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_DIR="$REPO_ROOT/ui/dashboard"

if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm is required to run the dashboard." >&2
  exit 1
fi

cd "$DASHBOARD_DIR"

if [[ ! -d node_modules ]]; then
  echo "Installing dashboard dependencies..."
  npm install
fi

npm run dev -- --host 127.0.0.1 --port 5173
