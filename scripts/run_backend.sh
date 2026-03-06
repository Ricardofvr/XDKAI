#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON_EXEC="$REPO_ROOT/.venv/bin/python"
else
  echo "Warning: .venv not found; using system python3. Run ./scripts/setup_venv.sh to create it." >&2
  PYTHON_EXEC="python3"
fi

"$PYTHON_EXEC" -m backend.main --config config/portable-ai-drive-pro.json
