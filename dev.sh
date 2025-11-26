#!/bin/bash

# Exit immediately if a command fails
set -e

#Main Server (8000) PID: 19702
#MCP (8001) PID: 19705
#WhatsApp (5050) PID: 19707
#Cloudflare Tunnel PID: 19710


# --- Configuration ---
TUNNEL_ID="646c5208-a422-4b8c-95de-8b58dae7b4fb"
VENV_PATH="/home/ubuntu/A2backend/venv/bin/activate"
MAIN_PORT=8000
MCP_PORT=8001
WHATSAPP_PORT=5050

# Public Hostnames for access (for user information)
FASTAPI_HOST="fastapi.graphsensesolutions.com"
MCP_HOST="mcp.graphsensesolutions.com"
WHATSAPP_HOST="whatsapp.graphsensesolutions.com"


# --- Start Services ---

echo "Activating virtual environment..."
source "$VENV_PATH"

echo "Starting main server (Uvicorn) on localhost:$MAIN_PORT..."
# Note: Using nohup and redirecting output to /dev/null to ensure it runs cleanly in the background
nohup uvicorn server.main:app --port $MAIN_PORT &> /dev/null &
SERVER_PID=$!
sleep 3 # Give Uvicorn time to start up

echo "Starting MCP (Python) on localhost:$MCP_PORT..."
nohup python3 mcp/main.py --http &> /dev/null &
MCP_PID=$!
sleep 3

echo "Starting WhatsApp service (Uvicorn) on localhost:$WHATSAPP_PORT..."
nohup uvicorn whatsapp.main:app --port $WHATSAPP_PORT &> /dev/null &
WHATSAPP_PID=$!
sleep 3

# --- Start Cloudflare Tunnel ---

# Start the tunnel using the ID. The credentials-file and ingress rules 
# will be picked up from the default config location (e.g., /etc/cloudflared/config.yml).
echo "Starting Cloudflare tunnel (ID: $TUNNEL_ID)..."
# We run the tunnel using 'nohup' so it runs in the background.
nohup cloudflared tunnel run "$TUNNEL_ID" &> /dev/null &
TUNNEL_PID=$!
sleep 5 # Give the tunnel more time to connect and register routes

# --- Status ---
echo "--- Process IDs ---"
echo "Main Server (8000) PID: $SERVER_PID"
echo "MCP (8001) PID: $MCP_PID"
echo "WhatsApp (5050) PID: $WHATSAPP_PID"
echo "Cloudflare Tunnel PID: $TUNNEL_PID"
echo "-------------------"

echo "--- Access URLs ---"
echo "FastAPI (8000): https://$FASTAPI_HOST"
echo "MCP (8001):     https://$MCP_HOST"
echo "WhatsApp (5050):https://$WHATSAPP_HOST"
echo "-------------------"

# --- Graceful Shutdown Handler ---

# Function to kill processes and exit
cleanup() {
    echo ""
    echo "Stopping all background processes..."
    
    # List of PIDs to stop
    PIDS=("$SERVER_PID" "$MCP_PID" "$WHATSAPP_PID" "$TUNNEL_PID")

    for pid in "${PIDS[@]}"; do
        if kill -0 $pid 2>/dev/null; then # Check if PID exists
            echo "Stopping PID $pid..."
            kill "$pid" 2>/dev/null || true
        fi
    done
    
    # Wait for all background jobs to finish
    wait 2>/dev/null
    echo "All processes stopped cleanly."
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM (kill) signals
trap cleanup SIGINT SIGTERM

# --- Keep Alive ---

echo "Script is running. Press Ctrl+C to stop all services and tunnel."
# The 'wait' command keeps the main script alive until a trapped signal is received
wait