import pytest
from datetime import datetime, timedelta

def test_create_task(api_client, auth_headers):
    payload = {
        "title": "API Test Task",
        "description": "Created via API test",
        "priority": "high",
        "deadline": (datetime.utcnow() + timedelta(days=1)).isoformat()
    }
    response = api_client.post("/tasks/", json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["title"] == "API Test Task"

def test_get_tasks(api_client, auth_headers):
    response = api_client.get("/tasks/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update_task(api_client, auth_headers):
    create_resp = api_client.post("/tasks/", json={"title": "Update Task"}, headers=auth_headers)
    task_id = create_resp.json()["id"]
    
    response = api_client.put(f"/tasks/{task_id}", json={"status": "in_progress"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"

def test_assign_task(api_client, auth_headers):
    # Create task
    task_resp = api_client.post("/tasks/", json={"title": "Assign Task"}, headers=auth_headers)
    task_id = task_resp.json()["id"]
    
    # Get current user id
    user_resp = api_client.get("/users/", headers=auth_headers)
    user_id = user_resp.json()[0]["id"]
    
    response = api_client.post(f"/tasks/{task_id}/assign", json={"user_id": user_id}, headers=auth_headers)
    assert response.status_code == 200
    assert "assigned successfully" in response.json()["message"]

def test_checklist_operations(api_client, auth_headers):
    # Create task
    task_resp = api_client.post("/tasks/", json={"title": "Checklist Task"}, headers=auth_headers)
    task_id = task_resp.json()["id"]
    
    # Add item
    add_resp = api_client.post(f"/tasks/{task_id}/checklist/add", json={"text": "Item 1"}, headers=auth_headers)
    assert add_resp.status_code == 200
    assert len(add_resp.json()["checklist"]) == 1
    
    # Update item
    upd_resp = api_client.put(f"/tasks/{task_id}/checklist/update", json={"index": 0, "completed": True}, headers=auth_headers)
    assert upd_resp.status_code == 200
    assert upd_resp.json()["checklist"][0]["completed"] is True
    
    # Remove item
    rem_resp = api_client.request("DELETE", f"/tasks/{task_id}/checklist/remove", json={"index": 0}, headers=auth_headers)
    assert rem_resp.status_code == 200
    assert len(rem_resp.json()["checklist"]) == 0

def test_cancel_task(api_client, auth_headers):
    create_resp = api_client.post("/tasks/", json={"title": "Cancel Task"}, headers=auth_headers)
    task_id = create_resp.json()["id"]
    
    response = api_client.post(f"/tasks/{task_id}/cancel", json={"cancellation_reason": "No longer needed"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
