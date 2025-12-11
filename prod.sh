#!/bin/bash

# Fail on undefined variables (safer than set -e)
set -u

# --- Configuration ---
TUNNEL_ID="646c5208-a422-4b8c-95de-8b58dae7b4fb"
VENV_PATH="/home/ubuntu/A2backend/venv/bin/activate"
LOG_DIR="/home/ubuntu/A2backend/logs"

MAIN_PORT=8000
MCP_PORT=8001
WHATSAPP_PORT=5050

echo "Activating virtual environment..."
source "$VENV_PATH"

mkdir -p "$LOG_DIR"

echo "Starting main FastAPI server..."
nohup uvicorn server.main:app --host 0.0.0.0 --port $MAIN_PORT \
    > "$LOG_DIR/main.out.log" \
    2> "$LOG_DIR/main.err.log" &
SERVER_PID=$!

echo "Starting MCP server..."
nohup python3 mcp/main.py --http \
    > "$LOG_DIR/mcp.out.log" \
    2> "$LOG_DIR/mcp.err.log" &
MCP_PID=$!

echo "Starting WhatsApp service..."
nohup uvicorn whatsapp.main:app --host 0.0.0.0 --port $WHATSAPP_PORT \
    > "$LOG_DIR/whatsapp.out.log" \
    2> "$LOG_DIR/whatsapp.err.log" &
WHATSAPP_PID=$!

echo "Starting Cloudflare tunnel..."
nohup cloudflared tunnel run "$TUNNEL_ID" \
    > "$LOG_DIR/tunnel.out.log" \
    2> "$LOG_DIR/tunnel.err.log" &
TUNNEL_PID=$!

# --- Graceful Shutdown ---
cleanup() {
    echo ""
    echo "Stopping all background processes..."
    for pid in "$SERVER_PID" "$MCP_PID" "$WHATSAPP_PID" "$TUNNEL_PID"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping PID $pid..."
            kill "$pid" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null
    echo "All processes stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "--- PIDs ---"
echo "Main       : $SERVER_PID"
echo "MCP        : $MCP_PID"
echo "WhatsApp   : $WHATSAPP_PID"
echo "Tunnel     : $TUNNEL_PID"
echo "------------"

echo ""
echo "Logs are available at: $LOG_DIR"
echo "All services started in background."