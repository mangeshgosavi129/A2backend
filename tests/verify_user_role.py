import sys
import os
import secrets
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.append(os.getcwd())

from server.main import app

client = TestClient(app)

def test_user_role_response():
    print("\nTesting GET /users Role Field...")
    
    # 1. Signup Owner
    phone = f"{secrets.randbelow(899999999) + 100000000}" 
    payload = {
        "name": "Role Test User",
        "phone": str(phone),
        "password": "password123",
        "org_name": f"Org_{secrets.token_hex(4)}",
        "department": "Engineering"
    }
    resp = client.post("/auth/signup", json=payload)
    if resp.status_code != 201:
        print(f"Signup failed: {resp.text}")
        return
    
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get Users
    resp = client.get("/users", headers=headers)
    if resp.status_code != 200:
        print(f"GET /users failed: {resp.text}")
        return
        
    users = resp.json()
    user = users[0]
    
    # 3. Verify Role
    print(f"User Response: {user}")
    if "role" in user and user["role"] == "owner":
        print("✅ Success: 'role' field present and correct.")
    else:
        print(f"❌ Failure: 'role' field missing or incorrect. Got: {user.get('role')}")

if __name__ == "__main__":
    test_user_role_response()
