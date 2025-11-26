#!/bin/bash

# Activate virtual environment
source /home/ubuntu/A2backend/venv/bin/activate

# Exit immediately if a command fails
set -e

# Ports used
SERVER_PORT=8000
MCP_PORT=8001
WHATSAPP_PORT=5050

# Function to kill process on a port if it exists
kill_port() {
    PORT=$1
    PID=$(lsof -t -i :$PORT)
    if [ -n "$PID" ]; then
        echo "Killing process $PID on port $PORT"
        kill -9 $PID
    fi
}

echo "Cleaning up old processes..."
kill_port $SERVER_PORT
kill_port $MCP_PORT
kill_port $WHATSAPP_PORT

sleep 1

# Start the main server on localhost:8000
echo "Starting main server on localhost:$SERVER_PORT..."
uvicorn server.main:app --port $SERVER_PORT &
SERVER_PID=$!
sleep 2

# Start MCP on localhost:8001
echo "Starting MCP on localhost:$MCP_PORT..."
python3 mcp/main.py --http &
MCP_PID=$!
sleep 2

# Start WhatsApp service on localhost:5050
echo "Starting WhatsApp service on localhost:$WHATSAPP_PORT..."
uvicorn whatsapp.main:app --port $WHATSAPP_PORT &
WHATSAPP_PID=$!
sleep 2

# Start Cloudflare Tunnel
echo "Starting Cloudflare tunnel..."
cloudflared tunnel run A2backend-tunnel &
TUNNEL_PID=$!
sleep 3

# Show PIDs
echo "Server PID: $SERVER_PID"
echo "MCP PID: $MCP_PID"
echo "WhatsApp PID: $WHATSAPP_PID"
echo "Tunnel PID: $TUNNEL_PID"

# Handle shutdown gracefully
trap 'echo "Stopping all processes..."; 
      for pid in $SERVER_PID $MCP_PID $WHATSAPP_PID $TUNNEL_PID; do
          if kill -0 $pid 2>/dev/null; then
              kill $pid 2>/dev/null || true
          fi
      done
      wait
      echo "All processes stopped cleanly."; 
      exit 0' SIGINT SIGTERM

# Keep script alive while background processes run
wait