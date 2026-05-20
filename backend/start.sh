#!/bin/bash
# Run this from anywhere inside the project.
# It automatically navigates to the project root and starts the server.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting IPL Akinator backend from: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

./backend/venv/bin/uvicorn backend.main:app --reload --port 8000
