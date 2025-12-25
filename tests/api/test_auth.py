import pytest
import httpx
import random
import string

BASE_URL = "http://localhost:8000"

def get_random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_random_phone():
    # 2 digits for country code (e.g., 91) + 10 digits for number
    return f"91{random.randint(1000000000, 9999999999)}"

@pytest.fixture
def api_client():
    return httpx.Client(base_url=BASE_URL, timeout=10.0)

def test_signup_create_org_success(api_client):
    phone = get_random_phone()
    org_name = f"TestOrg_{get_random_string(5)}"
    payload = {
        "name": "Test User",
        "phone": phone,
        "password": "password123",
        "org_name": org_name
    }
    response = api_client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_signup_join_org_success(api_client):
    # First create an org to ensure at least one exists
    phone1 = get_random_phone()
    org_name = f"OrgToJoin_{get_random_string(5)}"
    api_client.post("/auth/signup", json={
        "name": "Org Creator",
        "phone": phone1,
        "password": "password123",
        "org_name": org_name
    })
    
    # Now join an existing org (assuming ID 1 exists, which it should now)
    phone2 = get_random_phone()
    payload = {
        "name": "Joiner User",
        "phone": phone2,
        "password": "password123",
        "org_id": 1
    }
    response = api_client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    assert "access_token" in response.json()

def test_signup_invalid_phone(api_client):
    payload = {
        "name": "Test User",
        "phone": "91123456789", # 11 digits
        "password": "password123",
        "org_name": "SomeOrg"
    }
    response = api_client.post("/auth/signup", json=payload)
    assert response.status_code == 422 
    assert "Phone number must be exactly 12 digits" in response.text

def test_login_success(api_client):
    # First signup
    phone = get_random_phone()
    org_name = f"TestOrg_{get_random_string(5)}"
    signup_payload = {
        "name": "Login User",
        "phone": phone,
        "password": "secret_password",
        "org_name": org_name
    }
    api_client.post("/auth/signup", json=signup_payload)
    
    # Then login
    login_payload = {
        "phone": phone,
        "password": "secret_password"
    }
    response = api_client.post("/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

def test_logout_invalidation(api_client):
    # Signup and Login
    phone = get_random_phone()
    signup_payload = {
        "name": "Logout User",
        "phone": phone,
        "password": "password123",
        "org_name": f"LogoutOrg_{get_random_string(5)}"
    }
    api_client.post("/auth/signup", json=signup_payload)
    
    login_response = api_client.post("/auth/login", json={
        "phone": phone,
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Verify we can access a protected route (e.g. /users/me or just /auth/logout)
    # We'll use /auth/logout itself as it requires current_user
    logout_response = api_client.post("/auth/logout", headers=headers)
    assert logout_response.status_code == 200
    
    # Try to access again with same token
    second_logout = api_client.post("/auth/logout", headers=headers)
    assert second_logout.status_code == 401
    assert "Token has been invalidated" in second_logout.json()["detail"]

def test_login_failure(api_client):
    login_payload = {
        "phone": "910000000000",
        "password": "wrong_password"
    }
    response = api_client.post("/auth/login", json=login_payload)
    assert response.status_code == 401
