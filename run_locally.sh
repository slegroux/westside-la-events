#!/usr/bin/env bash
set -e

# Kill any existing server on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

cd "$(dirname "$0")"

eval "$(micromamba shell hook --shell bash)"
micromamba activate la
uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
