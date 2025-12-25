import pytest

def test_create_client(api_client, auth_headers):
    payload = {
        "name": "Test Client",
        "phone": "9876543210",
        "project_name": "Test Project"
    }
    response = api_client.post("/clients/", json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Test Client"

def test_get_clients(api_client, auth_headers):
    response = api_client.get("/clients/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update_client(api_client, auth_headers):
    # Create one first
    create_resp = api_client.post("/clients/", json={"name": "Temp Client"}, headers=auth_headers)
    client_id = create_resp.json()["id"]
    
    response = api_client.put(f"/clients/{client_id}", json={"name": "New Name"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"

def test_delete_client(api_client, auth_headers):
    create_resp = api_client.post("/clients/", json={"name": "Delete Me"}, headers=auth_headers)
    client_id = create_resp.json()["id"]
    
    response = api_client.delete(f"/clients/{client_id}", headers=auth_headers)
    assert response.status_code == 204
