import httpx
from typing import Optional
from fastmcp import FastMCP

from config import config

API_BASE = config.API_BASE
mcp = FastMCP("urbounce-tasks", port=8001)

SECRET_KEY = config.SECRET_KEY
ALGORITHM = "HS256"

def get_auth_headers(auth_token: str) -> dict:
    """
    Generate auth headers using the provided valid JWT token.
    """
    if auth_token:
        if not auth_token.startswith("Bearer "):
            return {"Authorization": f"Bearer {auth_token}"}
        return {"Authorization": auth_token}
        
    return {}

# =========================================================
# HELPER FUNCTION: Response Wrapper
# =========================================================
def mcp_response(success: bool, data: dict, instructions: str = "", error: str = None):
    """
    Standardized response format for all MCP tools.
    This helps the LLM understand what to do with the response.
    """
    response = {
        "success": success,
        "data": data if success else {},
    }
    if instructions:
        response["instructions"] = instructions
    if error:
        response["error"] = error
    return response

# =========================================================
# USER ENDPOINTS
# =========================================================
@mcp.tool()
async def list_users(auth_token: str):
    """List all users in your organisation. Use this to get the user_id of the assignee."""
    AUTH_HEADER = get_auth_headers(auth_token)
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get("/users")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_user(user_id: int, auth_token: str):
    """Get a user by ID"""
    AUTH_HEADER = get_auth_headers(auth_token)
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get(f"/users/{user_id}")
        if resp.status_code == 404:
            return {"error": "User not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

# @mcp.tool()
# async def update_user(user_id: int, name: Optional[str] = None, department: Optional[str] = None):
#     """Update a user's details"""
#     payload = {k: v for k, v in {"name": name, "department": department}.items() if v is not None}
#     async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
#         resp = await client.put(f"/users/{user_id}", json=payload)
#         if resp.status_code == 404:
#             return {"error": "User not found", "status": 404}
#         resp.raise_for_status()
#         return resp.json()

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
async def create_client(name: str, auth_token: str, phone: Optional[str] = None, project_name: Optional[str] = None):
    """Create a new client"""
    AUTH_HEADER = get_auth_headers(auth_token)
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
async def list_clients(auth_token: str):
    """List all clients"""
    AUTH_HEADER = get_auth_headers(auth_token)
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get("/clients")
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def get_client(client_id: int, auth_token: str):
    """Get a client by ID"""
    AUTH_HEADER = get_auth_headers(auth_token)
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        resp = await client.get(f"/clients/{client_id}")
        if resp.status_code == 404:
            return {"error": "Client not found", "status": 404}
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def update_client(client_id: int, auth_token: str, name: Optional[str] = None, phone: Optional[str] = None, project_name: Optional[str] = None):
    """Update a client's details"""
    AUTH_HEADER = get_auth_headers(auth_token)
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
async def create_and_assign_task(
    title: str,
    assignee_user_id: int,
    auth_token: str,
    client_id: Optional[int] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    deadline: Optional[str] = None,
    progress_percentage: Optional[int] = None
):
    """Create task AND assign to user in ONE operation. Use this when assignee is known.
    Status: assigned|in_progress|on_hold|completed|cancelled|overdue. Priority: high|medium|low
    All optional parameters have sensible defaults if not provided."""
    AUTH_HEADER = get_auth_headers(auth_token)
    try:
        # Step 1: Apply defaults and filter null values
        payload = {
            k: v for k, v in {
                "client_id": client_id,
                "title": title,
                "description": description,
                "status": status or "assigned",  # Default to assigned
                "priority": priority or "medium",  # Default to medium
                "deadline": deadline,
                "progress_percentage": progress_percentage if progress_percentage is not None else 0  # Default to 0
            }.items() if v is not None
        }
        
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
            # Create task
            resp = await client.post("/tasks", json=payload)
            resp.raise_for_status()
            task_data = resp.json()
            task_id = task_data["id"]
            
            # Step 2: Immediately assign to user
            assign_resp = await client.post(
                f"/tasks/{task_id}/assign",
                json={"user_id": assignee_user_id}
            )
            assign_resp.raise_for_status()
            
            return mcp_response(
                success=True,
                data=task_data,
                instructions=f"✓ Created & assigned task_id={task_id} to user {assignee_user_id}"
            )
    except httpx.HTTPStatusError as e:
        return mcp_response(
            success=False,
            data={},
            error=f"HTTP {e.response.status_code}: {e.response.text}"
        )
    except Exception as e:
        return mcp_response(
            success=False,
            data={},
            error=f"Error creating/assigning task: {str(e)}"
        )

@mcp.tool()
async def list_tasks(auth_token: str):
    """List all tasks. Cancelled tasks are excluded (soft deleted). Each task has 'id' for use with update_task, get_task, assign_task, etc."""
    AUTH_HEADER = get_auth_headers(auth_token)
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
            resp = await client.get("/tasks")
            resp.raise_for_status()
            tasks_data = resp.json()
            
            return mcp_response(
                success=True,
                data={"tasks": tasks_data, "count": len(tasks_data)},
                instructions=f"Found {len(tasks_data)} tasks"
            )
    except Exception as e:
        return mcp_response(
            success=False,
            data={},
            error=f"Error listing tasks: {str(e)}"
        )

@mcp.tool()
async def get_task(task_id: int, auth_token: str):
    """Get task by ID. Cancelled tasks are treated as soft deleted and will return 404."""
    AUTH_HEADER = get_auth_headers(auth_token)
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
            resp = await client.get(f"/tasks/{task_id}")
            
            if resp.status_code == 404:
                return mcp_response(
                    success=False,
                    data={},
                    error=f"Task {task_id} not found"
                )
            
            resp.raise_for_status()
            task_data = resp.json()
            
            return mcp_response(
                success=True,
                data=task_data,
                instructions=f"Retrieved task {task_id}"
            )
    except httpx.HTTPStatusError as e:
        return mcp_response(
            success=False,
            data={},
            error=f"HTTP {e.response.status_code}: {e.response.text}"
        )
    except Exception as e:
        return mcp_response(
            success=False,
            data={},
            error=f"Error getting task: {str(e)}"
        )



@mcp.tool()
async def update_task(
    task_id: int,
    auth_token: str, 
    title: Optional[str] = None, 
    description: Optional[str] = None, 
    status: Optional[str] = None,
    priority: Optional[str] = None,
    deadline: Optional[str] = None,
    end_datetime: Optional[str] = None,
    progress_description: Optional[str] = None,
    progress_percentage: Optional[int] = None
):
    """Use to update an existing task. Cancelled tasks cannot be updated (soft deleted).
    Use in scenarios where either a task is created without sufficient details and user adds them in successive messages or user simply wants to modify an existing task.
    Status: assigned|in_progress|on_hold|completed|cancelled|overdue. Priority: high|medium|low"""
    AUTH_HEADER = get_auth_headers(auth_token)
    try:
        # Filter out None values - already correct
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
                return mcp_response(
                    success=False,
                    data={},
                    error=f"Task {task_id} not found. Verify you're using the correct task_id from create_task response."
                )
            
            if resp.status_code == 403:
                return mcp_response(
                    success=False,
                    data={},
                    error=f"Task {task_id} cannot be updated. It may have been cancelled."
                )
            
            resp.raise_for_status()
            task_data = resp.json()
            
            return mcp_response(
                success=True,
                data=task_data,
                instructions=f"✓ Updated task {task_id}"
            )
    except httpx.HTTPStatusError as e:
        return mcp_response(
            success=False,
            data={},
            error=f"HTTP {e.response.status_code}: {e.response.text}"
        )
    except Exception as e:
        return mcp_response(
            success=False,
            data={},
            error=f"Error updating task: {str(e)}"
        )

@mcp.tool()
async def cancel_task(task_id: int, cancellation_reason: str, auth_token: str):
    """Cancel task with reason"""
    AUTH_HEADER = get_auth_headers(auth_token)
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
            resp = await client.post(
                f"/tasks/{task_id}/cancel",
                json={"cancellation_reason": cancellation_reason}
            )
            
            if resp.status_code == 404:
                return mcp_response(
                    success=False,
                    data={},
                    error=f"Task {task_id} not found"
                )
            
            resp.raise_for_status()
            task_data = resp.json()
            
            return mcp_response(
                success=True,
                data=task_data,
                instructions=f"✓ Cancelled {task_id}"
            )
    except httpx.HTTPStatusError as e:
        return mcp_response(
            success=False,
            data={},
            error=f"HTTP {e.response.status_code}: {e.response.text}"
        )
    except Exception as e:
        return mcp_response(
            success=False,
            data={},
            error=f"Error cancelling task: {str(e)}"
        )

# =========================================================
# TASK ASSIGNMENT ENDPOINTS
# =========================================================
# @mcp.tool()
# async def assign_task(task_id: int, user_id: int):
#     """Assign user to EXISTING task (use after create_task). To add assignee during creation, first call list_users() to get user_id, then include in create_task workflow. Idempotent."""
#     try:
#         async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
#             resp = await client.post(
#                 f"/tasks/{task_id}/assign",
#                 json={"user_id": user_id}
#             )
            
#             if resp.status_code == 404:
#                 return mcp_response(
#                     success=False,
#                     data={},
#                     error="Task or User not found. Verify task_id and user_id are correct."
#                 )
            
#             if resp.status_code == 400:
#                 # Note: Current backend returns 400 if already assigned in some cases
#                 # But according to server code, it's being made idempotent
#                 return mcp_response(
#                     success=False,
#                     data={},
#                     error="User already assigned to this task."
#                 )
            
#             resp.raise_for_status()
#             result = resp.json()
            
#             return mcp_response(
#                 success=True,
#                 data=result,
#                 instructions=f"✓ Assigned"
#             )
#     except httpx.HTTPStatusError as e:
#         return mcp_response(
#             success=False,
#             data={},
#             error=f"HTTP {e.response.status_code}: {e.response.text}"
#         )
#     except Exception as e:
#         return mcp_response(
#             success=False,
#             data={},
#             error=f"Error assigning task: {str(e)}"
#         )

# @mcp.tool()
# async def assign_task_multiple(task_id: int, user_ids: List[int]):
#     """Assign task to multiple users"""
#     try:
#         async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
#             resp = await client.post(
#                 f"/tasks/{task_id}/assign-multiple",
#                 json={"user_ids": user_ids}
#             )
            
#             if resp.status_code == 404:
#                 return mcp_response(
#                     success=False,
#                     data={},
#                     error="Task not found"
#                 )
            
#             resp.raise_for_status()
#             result = resp.json()
            
#             return mcp_response(
#                 success=True,
#                 data=result,
#                 instructions=f"✓ Assigned {len(user_ids)} users"
#             )
#     except Exception as e:
#         return mcp_response(
#             success=False,
#             data={},
#             error=f"Error assigning multiple users: {str(e)}"
#         )

# @mcp.tool()
# async def unassign_task(task_id: int, user_id: int):
#     """Unassign user from task"""
#     try:
#         async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
#             resp = await client.post(
#                 f"/tasks/{task_id}/unassign",
#                 json={"user_id": user_id}
#             )
            
#             if resp.status_code == 404:
#                 return mcp_response(
#                     success=False,
#                     data={},
#                     error="Assignment not found"
#                 )
            
#             resp.raise_for_status()
#             result = resp.json()
            
#             return mcp_response(
#                 success=True,
#                 data=result,
#                 instructions=f"✓ Unassigned"
#             )
#     except Exception as e:
#         return mcp_response(
#             success=False,
#             data={},
#             error=f"Error unassigning user: {str(e)}"
#         )

# =========================================================
# CHECKLIST ENDPOINTS
# =========================================================
@mcp.tool()
async def add_checklist_item(task_id: int, text: str, auth_token: str, completed: bool = False):
    """Add checklist item to task"""
    AUTH_HEADER = get_auth_headers(auth_token)
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
            resp = await client.post(
                f"/tasks/{task_id}/checklist/add",
                json={"text": text, "completed": completed}
            )
            
            if resp.status_code == 404:
                return mcp_response(
                    success=False,
                    data={},
                    error="Task not found"
                )
            
            resp.raise_for_status()
            task_data = resp.json()
            
            return mcp_response(
                success=True,
                data=task_data,
                instructions=f"✓ Item added"
            )
    except Exception as e:
        return mcp_response(
            success=False,
            data={},
            error=f"Error adding checklist item: {str(e)}"
        )

@mcp.tool()
async def update_checklist_item(task_id: int, index: int, auth_token: str, text: Optional[str] = None, completed: Optional[bool] = None):
    """Update a checklist item by index"""
    AUTH_HEADER = get_auth_headers(auth_token)
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
async def remove_checklist_item(task_id: int, index: int, auth_token: str):
    """Remove a checklist item by index"""
    AUTH_HEADER = get_auth_headers(auth_token)
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30, headers=AUTH_HEADER) as client:
        request = httpx.Request("DELETE", f"{API_BASE}/tasks/{task_id}/checklist/remove", json={"index": index}, headers=AUTH_HEADER)
        resp = await client.send(request)
        
        if resp.status_code == 404:
            return {"error": "Task not found", "status": 404}
        if resp.status_code == 400:
            return {"error": "Invalid index", "status": 400}
        resp.raise_for_status()
        return resp.json()

if __name__ == "__main__":
    import sys
    
    # Check if we want HTTP mode
    if "--http" in sys.argv:
        # Run as HTTP server
        port = "8001"
        host = "127.0.0.1"
        
        print(f"Starting MCP HTTP server on {host}:{port}")
        mcp.run(transport="sse")
    else:
        # Run as stdio (default for Claude Desktop)
        mcp.run()