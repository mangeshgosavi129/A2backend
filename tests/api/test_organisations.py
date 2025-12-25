import pytest

def test_get_organisations(api_client, auth_headers):
    response = api_client.get("/organisations/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "name" in data[0]

def test_get_specific_organisation(api_client, auth_headers):
    # Get org list first
    list_resp = api_client.get("/organisations/", headers=auth_headers)
    org_id = list_resp.json()[0]["id"]
    
    response = api_client.get(f"/organisations/{org_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == org_id

def test_get_org_roles(api_client, auth_headers):
    list_resp = api_client.get("/organisations/", headers=auth_headers)
    org_id = list_resp.json()[0]["id"]
    
    response = api_client.get(f"/organisations/{org_id}/roles", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
