#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=== Starting Echo Prototype ==="

# Check backend virtual environment
if [ ! -d "backend/.venv" ]; then
    echo "Creating virtual environment in backend/.venv..."
    python3 -m venv backend/.venv
    echo "Installing backend dependencies..."
    backend/.venv/bin/pip install -r backend/requirements.txt
fi

# Check frontend dependencies and build
if [ -f "frontend/package.json" ]; then
    if [ ! -d "frontend/node_modules" ]; then
        echo "Installing frontend dependencies..."
        (cd frontend && npm install)
    fi
    if [ ! -d "frontend/dist" ]; then
        echo "Building frontend production bundle..."
        (cd frontend && npm run build)
    fi
fi

echo "Starting Backend on http://localhost:8000 ..."
echo "Starting Frontend on http://localhost:3000 ..."

# Trap to kill background jobs on exit
trap 'kill $(jobs -p) 2>/dev/null' EXIT

# Start backend
(cd backend && .venv/bin/uvicorn main:app --reload --port 8000) &

# Start frontend (Vite dev server with hot-reload and API proxy)
if command -v npm >/dev/null 2>&1 && [ -f "frontend/package.json" ]; then
    (cd frontend && npm run dev -- --port 3000 --host) &
elif [ -d "frontend/dist" ]; then
    (cd frontend/dist && python3 -m http.server 3000) &
else
    (cd frontend && python3 -m http.server 3000) &
fi

echo "=================================================="
echo "Echo is running!"
echo " -> Frontend:  http://localhost:3000"
echo " -> Backend:   http://localhost:8000"
echo " -> Swagger:   http://localhost:8000/docs"
echo "=================================================="
echo "Press Ctrl+C to stop both servers."

wait
