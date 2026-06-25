#!/usr/bin/env bash
set -euo pipefail

echo "Starting Enterprise AI Assistant..."
echo "Frontend: http://localhost:8001"
echo "API docs: http://localhost:8001/docs"
echo ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
