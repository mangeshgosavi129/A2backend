import os
import httpx
from typing import Optional, List
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load .env from the same directory as this script
script_dir = Path(__file__).parent
dotenv_path = script_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Configuration
token = os.getenv("TOKEN")
print(f"DEBUG: Loaded token from {dotenv_path}: {token[:20] if token else None}...")
API_BASE = os.getenv("API_BASE", "https://fastapi.graphsensesolutions.com")
mcp = FastMCP("urbounce-tasks", port=8001)
AUTH_HEADER = {
    "Authorization": f"Bearer {token}"
}

# =========================================================
# USER ENDPOINTS
# =========================================================
@mcp.tool()
async def list_users():
    """List all users"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get("/users")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_user(user_id: int):
    """Get a user by ID"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get(f"/users/{user_id}")
        if resp.status_code == 404:
            return {"error": "User not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def update_user(user_id: int, name: Optional[str] = None, department: Optional[str] = None):
    """Update a user's details"""
    payload = {k: v for k, v in {"name": name, "department": department}.items() if v is not None}
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.put(f"/users/{user_id}", json=payload)
        if resp.status_code == 404:
            return {"error": "User not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

# @mcp.tool()#comment
# async def delete_user(user_id: int):
#     """Delete a user"""
#     async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
#         resp = await client.delete(f"/users/{user_id}")
#         if resp.status_code == 404:
#             return {"error": "User not found", "status": 404}
#         resp.raise_for_status()
#         return {"message": "User deleted successfully"}

# =========================================================
# CLIENT ENDPOINTS
# =========================================================
@mcp.tool()
async def create_client(name: str, phone: Optional[str] = None, project_name: Optional[str] = None):
    """Create a new client"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.post(
            "/clients",
            json={
                "name": name,
                "phone": phone,
                "project_name": project_name
            }
        )
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def list_clients():
    """List all clients"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get("/clients")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_client(client_id: int):
    """Get a client by ID"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get(f"/clients/{client_id}")
        if resp.status_code == 404:
            return {"error": "Client not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def update_client(client_id: int, name: Optional[str] = None, phone: Optional[str] = None, project_name: Optional[str] = None):
    """Update a client's details"""
    payload = {
        k: v for k, v in {
            "name": name,
            "phone": phone,
            "project_name": project_name
        }.items() if v is not None
    }
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.put(f"/clients/{client_id}", json=payload)
        if resp.status_code == 404:
            return {"error": "Client not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

# @mcp.tool()#comment
# async def delete_client(client_id: int):
#     """Delete a client"""
#     async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
#         resp = await client.delete(f"/clients/{client_id}")
#         if resp.status_code == 404:
#             return {"error": "Client not found", "status": 404}
#         resp.raise_for_status()
#         return {"message": "Client deleted successfully"}

# =========================================================
# TASK ENDPOINTS
# =========================================================
@mcp.tool()
async def create_task(
    title: str, 
    client_id: Optional[int] = None,
    description: Optional[str] = None, 
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get("/tasks")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_task(task_id: int):
    """Get a task by ID"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get(f"/tasks/{task_id}")
        if resp.status_code == 404:
            return {"error": "Task not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def update_task(
    task_id: int, 
    title: Optional[str] = None, 
    description: Optional[str] = None, 
    status: Optional[str] = None,
    priority: Optional[str] = None,
    deadline: Optional[str] = None,
    end_datetime: Optional[str] = None,
    progress_description: Optional[str] = None,
    progress_percentage: Optional[int] = None
):
    """Update a task"""
    payload = {
        k: v
        for k, v in {
            "title": title,
            "description": description,
            "status": status,
            "priority": priority,
            "deadline": deadline,
            "end_datetime": end_datetime,
            "progress_description": progress_description,
            "progress_percentage": progress_percentage
        }.items()
        if v is not None
    }
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.put(f"/tasks/{task_id}", json=payload)
        if resp.status_code == 404:
            return {"error": "Task not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def cancel_task(task_id: int, cancellation_reason: str):
    """Cancel a task"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.post(
            f"/tasks/{task_id}/cancel",
            json={"cancellation_reason": cancellation_reason}
        )
        if resp.status_code == 404:
            return {"error": "Task not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

# =========================================================
# TASK ASSIGNMENT ENDPOINTS
# =========================================================
@mcp.tool()
async def assign_task(task_id: int, user_id: int):
    """Assign a task to a user"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.post(
            f"/tasks/{task_id}/assign",
            json={"user_id": user_id}
        )
        if resp.status_code == 404:
            return {"error": "Task or User not found", "status": 404}
        if resp.status_code == 400:
            return {"error": "User already assigned", "status": 400}
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def assign_task_multiple(task_id: int, user_ids: List[int]):
    """Assign a task to multiple users"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.post(
            f"/tasks/{task_id}/assign-multiple",
            json={"user_ids": user_ids}
        )
        if resp.status_code == 404:
            return {"error": "Task not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def unassign_task(task_id: int, user_id: int):
    """Unassign a user from a task"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.post(
            f"/tasks/{task_id}/unassign",
            json={"user_id": user_id}
        )
        if resp.status_code == 404:
            return {"error": "Assignment not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

# =========================================================
# CHECKLIST ENDPOINTS
# =========================================================
@mcp.tool()
async def add_checklist_item(task_id: int, text: str, completed: bool = False):
    """Add an item to the task's checklist"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.post(
            f"/tasks/{task_id}/checklist/add",
            json={"text": text, "completed": completed}
        )
        if resp.status_code == 404:
            return {"error": "Task not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def update_checklist_item(task_id: int, index: int, text: Optional[str] = None, completed: Optional[bool] = None):
    """Update a checklist item by index"""
    payload = {
        k: v for k, v in {"index": index, "text": text, "completed": completed}.items() if v is not None
    }
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.put(
            f"/tasks/{task_id}/checklist/update",
            json=payload
        )
        if resp.status_code == 404:
            return {"error": "Task not found", "status": 404}
        if resp.status_code == 400:
            return {"error": "Invalid index", "status": 400}
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def remove_checklist_item(task_id: int, index: int):
    """Remove a checklist item by index"""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        request = httpx.Request("DELETE", f"{API_BASE}/tasks/{task_id}/checklist/remove", json={"index": index}, headers=AUTH_HEADER)
        resp = await client.send(request)
        
        if resp.status_code == 404:
            return {"error": "Task not found", "status": 404}
        if resp.status_code == 400:
            return {"error": "Invalid index", "status": 400}
        resp.raise_for_status()
        return resp.json()

# =========================================================
# MESSAGE ENDPOINTS
# =========================================================

# @mcp.tool()#comment
# async def create_message(
#     direction: str,
#     channel: str,
#     user_id: Optional[int] = None,
#     task_id: Optional[int] = None,
#     message_text: Optional[str] = None,
#     payload: Optional[dict] = None
# ):
#     """Create a message. Direction: in, out, system. Channel: whatsapp, web, system."""
#     async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
#         resp = await client.post(
#             "/messages",
#             json={
#                 "user_id": user_id,
#                 "task_id": task_id,
#                 "direction": direction,
#                 "channel": channel,
#                 "message_text": message_text,
#                 "payload": payload
#             }
#         )
#         resp.raise_for_status()
#         return resp.json()

# @mcp.tool()#comment
# async def list_messages(
#     user_id: Optional[int] = None,
#     task_id: Optional[int] = None,
#     direction: Optional[str] = None,
#     channel: Optional[str] = None
# ):
#     """List messages with optional filters"""
#     params = {
#         k: v for k, v in {
#             "user_id": user_id,
#             "task_id": task_id,
#             "direction": direction,
#             "channel": channel
#         }.items() if v is not None
#     }
#     async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
#         resp = await client.get("/messages", params=params)
#         resp.raise_for_status()
#         return resp.json()

if __name__ == "__main__":
    import sys
    
    # Check if we want HTTP mode
    if "--http" in sys.argv:
        # Run as HTTP server
        port = int(os.getenv("MCP_PORT", "8001"))
        host = os.getenv("MCP_HOST", "0.0.0.0")
        
        print(f"Starting MCP HTTP server on {host}:{port}")
        mcp.run(transport="sse")
    else:
        # Run as stdio (default for Claude Desktop)
        mcp.run()