def test_liveness(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness_when_database_available(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_fails_without_database(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "missing.db"))
    assert client.get("/readyz").status_code == 503


def test_liveness_does_not_depend_on_database(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "missing.db"))
    assert client.get("/healthz").status_code == 200


def test_simulated_readiness_failure(client, monkeypatch):
    """Escenario de mal despliegue: la versión nunca pasa a Ready, pero sigue viva."""
    monkeypatch.setenv("SIMULATE_READINESS_FAILURE", "true")
    assert client.get("/readyz").status_code == 503
    assert client.get("/healthz").status_code == 200
