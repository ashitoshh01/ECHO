#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=== Starting Echo Prototype ==="

# Check virtual environment
if [ ! -d "echo/backend/.venv" ]; then
    echo "Creating virtual environment in echo/backend/.venv..."
    python3 -m venv echo/backend/.venv
    echo "Installing backend dependencies..."
    echo/backend/.venv/bin/pip install -r echo/backend/requirements.txt
fi

echo "Starting Backend on http://localhost:8000 ..."
echo "Starting Frontend on http://localhost:3000 ..."

# Trap to kill background jobs on exit
trap 'kill $(jobs -p) 2>/dev/null' EXIT

# Start backend
(cd echo/backend && .venv/bin/uvicorn main:app --port 8000) &

# Start frontend
(cd echo/frontend && python3 -m http.server 3000) &

echo "=================================================="
echo "Echo is running!"
echo " -> Frontend:  http://localhost:3000"
echo " -> Backend:   http://localhost:8000"
echo " -> Swagger:   http://localhost:8000/docs"
echo "=================================================="
echo "Press Ctrl+C to stop both servers."

wait

