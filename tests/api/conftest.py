import pytest
import httpx
import random
import string

BASE_URL = "http://localhost:8000"

def get_random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_random_phone():
    return f"9{random.randint(100000000, 999999999)}"

@pytest.fixture
def api_client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0, follow_redirects=True) as client:
        yield client

@pytest.fixture
def auth_token(api_client):
    phone = get_random_phone()
    org_name = f"TestOrg_{get_random_string(5)}"
    payload = {
        "name": "Auth User",
        "phone": phone,
        "password": "password123",
        "org_name": org_name
    }
    response = api_client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    return response.json()["access_token"]

@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
