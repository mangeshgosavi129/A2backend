import sys
import os
import secrets
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.append(os.getcwd())

from server.main import app, get_db

client = TestClient(app)

# Helper to generate random string
def random_string(length=10):
    return secrets.token_hex(length // 2)

def setup_org(role="owner"):
    """Setup an Org and User with specific role"""
    print(f"\n--- Setup Org with {role} ---")
    org_name = f"Org_RBAC_{role}_{random_string()}"
    phone = f"{secrets.randbelow(899999999) + 100000000}" 
    
    # Signup (creates Owner)
    payload = {
        "name": f"User {role}",
        "phone": str(phone),
        "password": "password123",
        "org_name": org_name,
        "department": "Engineering"
    }
    resp = client.post("/auth/signup", json=payload)
    if resp.status_code != 201:
        print(f"Signup failed: {resp.text}")
        return None
    
    owner_token = resp.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    
    # Get details
    users = client.get("/users", headers=owner_headers).json()
    org_id = users[0]["org_id"]
    owner_id = users[0]["id"]
    
    if role == "owner":
        return {"headers": owner_headers, "user_id": owner_id, "org_id": org_id, "token": owner_token}
    
    # Create another user for the desired role
    phone_role = f"{secrets.randbelow(899999999) + 100000000}" 
    user_payload = {
        "name": f"Role User {role}",
        "phone": str(phone_role),
        "password": "password123",
        "org_id": org_id,
        "department": "Engineering"
    }
    resp = client.post("/auth/signup", json=user_payload)
    token = resp.json()["access_token"]
    role_headers = {"Authorization": f"Bearer {token}"}
    
    # Get ID
    users = client.get("/users", headers=owner_headers).json() # Owner lists users
    target_user = next(u for u in users if u["phone"] == str(phone_role))
    
    # Assign Role
    role_payload = {"user_id": target_user["id"], "role": role}
    client.post(f"/organisations/{org_id}/roles", json=role_payload, headers=owner_headers)
    
    return {"headers": role_headers, "user_id": target_user["id"], "org_id": org_id}


def test_rbac_intern_delete_user():
    print("\nTesting Intern Deleting User (Should Fail)...")
    intern = setup_org("intern")
    
    # Intern tries to delete themselves (or anyone)
    resp = client.delete(f"/users/{intern['user_id']}", headers=intern["headers"])
    if resp.status_code == 403:
        print("✅ Intern Delete User: Permission Denied (Pass)")
    else:
        print(f"❌ Intern Delete User Failed: Expected 403, got {resp.status_code}")

def test_rbac_manager_assign_task():
    print("\nTesting Manager Assigning Task (Should Pass)...")
    manager = setup_org("manager")
    
    # Create Task
    task_payload = {"title": "Manager Task", "priority": "high"}
    t_resp = client.post("/tasks", json=task_payload, headers=manager["headers"])
    task_id = t_resp.json()["id"]
    
    # Assign to self
    assign_payload = {"user_id": manager["user_id"]}
    resp = client.post(f"/tasks/{task_id}/assign", json=assign_payload, headers=manager["headers"])
    if resp.status_code == 200:
        print("✅ Manager Assign Task: Success (Pass)")
    else:
        print(f"❌ Manager Assign Task Failed: {resp.status_code} {resp.text}")

def test_rbac_employee_assign_task():
    print("\nTesting Employee Assigning Task (Should Fail)...")
    employee = setup_org("employee")
    
    # Create Task
    task_payload = {"title": "Employee Task", "priority": "medium"}
    t_resp = client.post("/tasks", json=task_payload, headers=employee["headers"])
    task_id = t_resp.json()["id"]
    
    # Assign to self
    assign_payload = {"user_id": employee["user_id"]}
    resp = client.post(f"/tasks/{task_id}/assign", json=assign_payload, headers=employee["headers"])
    if resp.status_code == 403:
        print("✅ Employee Assign Task: Permission Denied (Pass)")
    else:
        print(f"❌ Employee Assign Task Failed: Expected 403, got {resp.status_code}")

def test_checklist_access():
    print("\nTesting Checklist Access...")
    # Setup Owner (Assigner) and Intern (Assignee)
    owner = setup_org("owner")
    
    # Create Intern user
    phone_intern = f"{secrets.randbelow(899999999) + 100000000}"
    client.post("/auth/signup", json={
        "name": "Intern", "phone": str(phone_intern), "password": "pass", 
        "org_id": owner["org_id"]
    })
    # Login as Intern
    resp = client.post("/auth/login", json={"phone": str(phone_intern), "password": "pass"})
    intern_token = resp.json()["access_token"]
    intern_headers = {"Authorization": f"Bearer {intern_token}"}
    
    # Get Intern ID
    users = client.get("/users", headers=owner["headers"]).json()
    intern_id = next(u for u in users if u["phone"] == str(phone_intern))["id"]
    
    # Create Task
    t_resp = client.post("/tasks", json={"title": "Checklist Task"}, headers=owner["headers"])
    task_id = t_resp.json()["id"]
    
    # Assign to Intern
    client.post(f"/tasks/{task_id}/assign", json={"user_id": intern_id}, headers=owner["headers"])
    
    # Intern adds checklist item (Should Pass - Assigned)
    resp = client.post(f"/tasks/{task_id}/checklist/add", json={"text": "Item 1"}, headers=intern_headers)
    if resp.status_code == 200:
        print("✅ Assigned Intern Add Checklist: Success (Pass)")
    else:
        print(f"❌ Assigned Intern Add Checklist Failed: {resp.status_code}")

    # Another employee (Unassigned)
    phone_emp = f"{secrets.randbelow(899999999) + 100000000}"
    client.post("/auth/signup", json={
        "name": "Emp", "phone": str(phone_emp), "password": "pass", 
        "org_id": owner["org_id"]
    })
    # Set role to Employee
    users = client.get("/users", headers=owner["headers"]).json()
    emp_id = next(u for u in users if u["phone"] == str(phone_emp))["id"]
    client.post(f"/organisations/{owner['org_id']}/roles", json={"user_id": emp_id, "role": "employee"}, headers=owner["headers"])
    
    resp = client.post("/auth/login", json={"phone": str(phone_emp), "password": "pass"})
    emp_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    
    # Unassigned Employee adds checklist item (Should Fail)
    resp = client.post(f"/tasks/{task_id}/checklist/add", json={"text": "Item 2"}, headers=emp_headers)
    if resp.status_code == 403:
        print("✅ Unassigned Employee Add Checklist: Permission Denied (Pass)")
    else:
        print(f"❌ Unassigned Employee Add Checklist Failed: Expected 403, got {resp.status_code}")

if __name__ == "__main__":
    try:
        test_rbac_intern_delete_user()
        test_rbac_manager_assign_task()
        test_rbac_employee_assign_task()
        test_checklist_access()
        print("\n🎉 RBAC Tests Completed")
    except Exception as e:
        import traceback
        traceback.print_exc()
