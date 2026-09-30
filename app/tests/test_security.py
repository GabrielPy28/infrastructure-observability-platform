import pytest

API_KEY = "test-key"


@pytest.fixture
def secured_client(client, monkeypatch):
    monkeypatch.setenv("API_KEY", API_KEY)
    return client


def test_api_is_open_without_configured_key(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    assert client.get("/api/v1/servers").status_code == 200


def test_missing_api_key_is_rejected(secured_client):
    response = secured_client.get("/api/v1/servers")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "ApiKey"


def test_wrong_api_key_is_rejected(secured_client):
    assert secured_client.get("/api/v1/servers", headers={"X-API-Key": "wrong"}).status_code == 401


def test_valid_api_key_is_accepted(secured_client):
    assert secured_client.get("/api/v1/servers", headers={"X-API-Key": API_KEY}).status_code == 200


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
def test_health_endpoints_do_not_require_api_key(secured_client, path):
    assert secured_client.get(path).status_code == 200
