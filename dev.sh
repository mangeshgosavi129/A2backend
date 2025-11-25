#!/bin/bash

# Exit immediately if a command fails
set -e

# Start the main server on localhost:8000
echo "Starting main server on localhost:8000..."
# Run your server command here (replace with actual)
uvicorn server.main:app --port 8000 &
SERVER_PID=$!
sleep 2

# Start MCP on localhost:8001
echo "Starting MCP on localhost:8001..."
python3 mcp/main.py --http &
MCP_PID=$!
sleep 2

# Start WhatsApp service on localhost:5050
echo "Starting WhatsApp service on localhost:5050..."
uvicorn whatsapp.main:app --port 5050 &
WHATSAPP_PID=$!
sleep 3

# Start Frontend on localhost:3000
echo "Starting Frontend on localhost:3000..."
cd frontend && npm install --legacy-peer-deps && npm run dev &
FRONTEND_PID=$!
cd ..
sleep 3

echo "Starting ngrok tunnels..."
ngrok start --all --config=ngrok.yml &
NGROK_PID=$!

sleep 3
echo "Fetching MCP ngrok public URL..."
MCP_URL=$(curl --silent http://127.0.0.1:4040/api/tunnels | grep -o '"public_url":"[^"]*"' | grep https | head -n 1 | cut -d '"' -f4)
echo "MCP available at: $MCP_URL"

# Handle shutdown gracefully
trap 'echo "Stopping all processes..."; 
      for pid in $SERVER_PID $MCP_PID $WHATSAPP_PID $NGROK_PID $FRONTEND_PID; do
          if kill -0 $pid 2>/dev/null; then
              kill $pid 2>/dev/null || true
          fi
      done
      wait
      echo "All processes stopped cleanly."; 
      exit 0' SIGINT

# Keep script alive while background processes run
wait