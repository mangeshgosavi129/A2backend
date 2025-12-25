import pytest

def test_internal_get_user(api_client, auth_headers):
    # Get a real user first from the public API
    user_resp = api_client.get("/users/", headers=auth_headers)
    user = user_resp.json()[0]
    phone = user["phone"]
    
    # Test internal lookup by phone
    response = api_client.get(f"/internals/user?phone={phone}")
    assert response.status_code == 200
    assert response.json()["id"] == user["id"]

def test_internal_check_idempotency(api_client):
    # Check non-existent ID
    response = api_client.get("/internals/idempotency/non_existent_id")
    assert response.status_code == 200
    assert response.json()["exists"] is False

def test_internal_store_message(api_client, auth_headers):
    # Get user id
    user_resp = api_client.get("/users/", headers=auth_headers)
    user_id = user_resp.json()[0]["id"]
    
    payload = {
        "user_id": user_id,
        "direction": "in",
        "channel": "whatsapp",
        "message_text": "Internal test message",
        "payload": {"whatsapp_id": "test_wa_id"}
    }
    response = api_client.post("/internals/message", json=payload)
    assert response.status_code == 200 # Note: internals/message returns 200, not 201 in the code
    assert response.json()["message_text"] == "Internal test message"

def test_internal_get_history(api_client, auth_headers):
    user_resp = api_client.get("/users/", headers=auth_headers)
    user_id = user_resp.json()[0]["id"]
    
    response = api_client.get(f"/internals/history/{user_id}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
