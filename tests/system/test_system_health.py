def test_root_index_page(client):
    """System test: Verify root dashboard loads successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Kotak Neo Personal Trading Terminal" in response.data
    assert b"Phase 1 - Project Skeleton Ready" in response.data


def test_api_health_endpoint(client):
    """System test: Verify system health API response."""
    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["data"]["phase"] == "phase_1_skeleton"


def test_api_feature_flags_endpoint(client):
    """System test: Verify feature flags endpoint returns valid map."""
    response = client.get("/api/settings/feature-flags")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "PAPER_TRADING" in data["data"]


def test_404_error_handler(client):
    """System test: Verify unmapped routes trigger standard JSON error response."""
    response = client.get("/api/non-existent-route")
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"
    assert data["error_code"] == "HTTP_404"

