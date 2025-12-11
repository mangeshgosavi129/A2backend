#!/bin/bash

# Fail on undefined variables
set -u

# Resolve current script directory
CUR_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Configuration ---
VENV_PATH="$CUR_DIR/.venv/bin/activate"
LOG_DIR="$CUR_DIR/logs"

MAIN_PORT=8000

echo "Activating virtual environment..."
source "$VENV_PATH"

mkdir -p "$LOG_DIR"

echo "Starting main FastAPI server..."
nohup uvicorn server.main:app --host 0.0.0.0 --port $MAIN_PORT \
    > "$LOG_DIR/main.out.log" \
    2> "$LOG_DIR/main.err.log" &
SERVER_PID=$!

# --- Graceful Shutdown ---
cleanup() {
    echo ""
    echo "Stopping FastAPI server..."
    if kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null
    echo "FastAPI server stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "--- DEV MODE PIDs ---"
echo "Main FastAPI : $SERVER_PID"
echo "----------------------"

echo ""
echo "Logs are available at: $LOG_DIR"
echo "Dev FastAPI server started in background."