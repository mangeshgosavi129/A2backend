import pytest

def test_prometheus_metrics(api_client):
    response = api_client.get("/metrics/")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
