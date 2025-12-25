import pytest

def test_create_message(api_client, auth_headers):
    payload = {
        "direction": "in",
        "channel": "whatsapp",
        "message_text": "Hello from test"
    }
    response = api_client.post("/messages/", json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["message_text"] == "Hello from test"

def test_get_messages(api_client, auth_headers):
    response = api_client.get("/messages/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
