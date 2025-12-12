import sys
import os
import secrets
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.append(os.getcwd())

from server.main import app, get_db

# Helper to generate random string
def random_string(length=10):
    return secrets.token_hex(length // 2)

client = TestClient(app)

def setup_org(name_prefix):
    """Setup an Org and User"""
    print(f"\n--- Setup {name_prefix} ---")
    org_name = f"{name_prefix}_{random_string()}"
    phone = f"{secrets.randbelow(899999999) + 100000000}" 
    
    # Signup User
    payload = {
        "name": f"User {name_prefix}",
        "phone": str(phone),
        "password": "password123",
        "org_name": org_name,
        "department": "Engineering"
    }
    resp = client.post("/auth/signup", json=payload)
    if resp.status_code != 201:
        print(f"Failed to signup User {name_prefix}: {resp.status_code} {resp.text}")
        return None
    
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get User ID and Org ID
    users_resp = client.get("/users", headers=headers)
    users = users_resp.json()
    user_id = users[0]["id"]
    org_id = users[0]["org_id"]
    
    return {"token": token, "user_id": user_id, "org_id": org_id, "headers": headers}

def test_user_isolation(org_a, org_b):
    """Verify User B cannot access User A's data"""
    print("\nTesting User Isolation...")
    user_a_id = org_a["user_id"]
    
    # User B tries to get User A
    resp = client.get(f"/users/{user_a_id}", headers=org_b["headers"])
    if resp.status_code == 404:
        print("✅ GET /users/{id} isolation passed")
    else:
        print(f"❌ GET /users/{id} isolation FAILED. Status: {resp.status_code}")

    # User B tries to update User A
    resp = client.put(f"/users/{user_a_id}", json={"name": "Hacked"}, headers=org_b["headers"])
    if resp.status_code == 404:
        print("✅ PUT /users/{id} isolation passed")
    else:
        print(f"❌ PUT /users/{id} isolation FAILED. Status: {resp.status_code}")

    # User B tries to delete User A
    resp = client.delete(f"/users/{user_a_id}", headers=org_b["headers"])
    if resp.status_code == 404:
        print("✅ DELETE /users/{id} isolation passed")
    else:
        print(f"❌ DELETE /users/{id} isolation FAILED. Status: {resp.status_code}")

def test_task_isolation(org_a, org_b):
    """Verify User B cannot access/modify User A's tasks"""
    print("\nTesting Task Isolation...")
    
    # User A creates a task
    task_payload = {
        "title": "Secret Task A",
        "description": "Top Secret",
        "priority": "high",
        "deadline": "2023-12-31T23:59:59"
    }
    resp = client.post("/tasks", json=task_payload, headers=org_a["headers"])
    if resp.status_code != 201:
        print(f"Failed to create setup task in Org A: {resp.text}")
        return

    task_id = resp.json()["id"]
    
    # User B tries to get Task A
    resp = client.get(f"/tasks/{task_id}", headers=org_b["headers"])
    if resp.status_code == 404:
        print("✅ GET /tasks/{id} isolation passed")
    else:
        print(f"❌ GET /tasks/{id} isolation FAILED. Status: {resp.status_code}")
    
    # User B tries to assign themselves to Task A
    assign_payload = {"user_id": org_b["user_id"]}
    resp = client.post(f"/tasks/{task_id}/assign", json=assign_payload, headers=org_b["headers"])
    if resp.status_code == 404:
        print("✅ POST /tasks/{id}/assign isolation passed")
    else:
        print(f"❌ POST /tasks/{id}/assign isolation FAILED. Status: {resp.status_code} - {resp.text}")
    
    # User B tries to add checklist to Task A
    checklist_payload = {"text": "Malicious Item"}
    resp = client.post(f"/tasks/{task_id}/checklist/add", json=checklist_payload, headers=org_b["headers"])
    if resp.status_code == 404:
         print("✅ POST /tasks/{id}/checklist/add isolation passed")
    else:
         print(f"❌ POST /tasks/{id}/checklist/add isolation FAILED. Status: {resp.status_code}")

def test_message_isolation(org_a, org_b):
    print("\nTesting Message Isolation...")
    
    msg_payload = {
        "direction": "out",
        "channel": "web",
        "message_text": "Hello Org A"
    }
    resp = client.post("/messages", json=msg_payload, headers=org_a["headers"])
    if resp.status_code != 201:
        print(f"Failed to create message in Org A: {resp.text}")
        return

    msg_id = resp.json()["id"]
    
    resp = client.get("/messages", headers=org_b["headers"])
    if resp.status_code == 200:
        messages = resp.json()
        if not any(m["id"] == msg_id for m in messages):
            print("✅ GET /messages isolation passed")
        else:
            print("❌ GET /messages isolation FAILED. Org A message found in Org B's list.")
    else:
        print(f"❌ GET /messages Failed. Status: {resp.status_code}")

if __name__ == "__main__":
    try:
        print("Starting Tenant Isolation Tests with TestClient...")
        org_a = setup_org("OrgA")
        if not org_a:
            sys.exit(1)
            
        org_b = setup_org("OrgB")
        if not org_b:
            sys.exit(1)
            
        test_user_isolation(org_a, org_b)
        test_task_isolation(org_a, org_b)
        test_message_isolation(org_a, org_b)
        print("\n🎉 ALL TESTS COMPLETED")
    except Exception as e:
        import traceback
        traceback.print_exc()
