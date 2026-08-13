"""
Integration tests for the health endpoint.

Tests the full HTTP request → response flow via FastAPI TestClient.
"""


class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    def test_health_returns_200(self, test_client):
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_response_structure(self, test_client):
        response = test_client.get("/api/v1/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_health_returns_correct_version(self, test_client):
        response = test_client.get("/api/v1/health")
        data = response.json()
        assert data["version"] == "0.1.0"
