#!/bin/bash

# Exit immediately if a command fails
set -e

# Kill leftover processes on required ports
echo "Cleaning up old processes..."
for port in 8000 8001 5050; do
    PIDS=$(sudo lsof -ti :$port)
    if [ ! -z "$PIDS" ]; then
        echo "Killing processes on port $port: $PIDS"
        sudo kill -9 $PIDS
    fi
done

sleep 1

# Start the main FastAPI server on localhost:8000
echo "Starting main server on localhost:8000..."
uvicorn server.main:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!
sleep 2

# Start MCP server on localhost:8001
echo "Starting MCP server on localhost:8001..."
uvicorn mcp.main:app --host 127.0.0.1 --port 8001 &
MCP_PID=$!
sleep 2

# Start WhatsApp service on localhost:5050
echo "Starting WhatsApp service on localhost:5050..."
uvicorn whatsapp.main:app --host 127.0.0.1 --port 5050 &
WHATSAPP_PID=$!
sleep 2

# Start Cloudflared tunnel
echo "Starting Cloudflare tunnel..."
cloudflared tunnel run A2backend-tunnel &
CLOUDFLARE_PID=$!
sleep 5

echo "All services started."
echo "FastAPI: https://fastapi.graphsensesolutions.com"
echo "MCP: https://mcp.graphsensesolutions.com"
echo "WhatsApp: https://whatsapp.graphsensesolutions.com"

# Graceful shutdown
trap 'echo "Stopping all processes...";
      for pid in $SERVER_PID $MCP_PID $WHATSAPP_PID $CLOUDFLARE_PID; do
          if kill -0 $pid 2>/dev/null; then
              kill $pid 2>/dev/null || true
          fi
      done
      wait
      echo "All processes stopped cleanly.";
      exit 0' SIGINT SIGTERM

# Keep script alive while background processes run
wait