#!/bin/bash

# Exit immediately if a command fails
set -e

# Activate virtual environment
source /home/ubuntu/A2backend/venv/bin/activate

echo "Starting main server on localhost:8000..."
uvicorn server.main:app --port 8000 &
SERVER_PID=$!
sleep 2

echo "Starting MCP on localhost:8001..."
python3 mcp/main.py --http &
MCP_PID=$!
sleep 2

echo "Starting WhatsApp service on localhost:5050..."
uvicorn whatsapp.main:app --port 5050 &
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