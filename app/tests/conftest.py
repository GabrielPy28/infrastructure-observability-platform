import pytest
from fastapi.testclient import TestClient

from seed.generate import build_database


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    """Genera una vez la misma base de datos determinista que se empaqueta en la imagen."""
    return build_database(tmp_path_factory.mktemp("data") / "infra.db")


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(db_path))
    from src.main import app

    with TestClient(app) as test_client:
        yield test_client
