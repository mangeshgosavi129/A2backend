import pytest

def test_get_users(api_client, auth_headers):
    response = api_client.get("/users/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_me(api_client, auth_headers):
    # Auth user can't directly get "me" via /users/me in this schema? 
    # Let's check users.py again. Ah, it has get_users with filters, but no explicit /me.
    # Wait, I see get_user(user_id) but no /me. 
    # Let me check the user list and get the first one.
    list_resp = api_client.get("/users/", headers=auth_headers)
    users = list_resp.json()
    assert len(users) > 0
    
    user_id = users[0]["id"]
    response = api_client.get(f"/users/{user_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == user_id

def test_update_user(api_client, auth_headers):
    list_resp = api_client.get("/users/", headers=auth_headers)
    user_id = list_resp.json()[0]["id"]
    
    payload = {"name": "Updated Name"}
    response = api_client.put(f"/users/{user_id}", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"
