import pytest

from seed.generate import COUNTS, DATACENTERS, build_database


def test_seed_is_deterministic(tmp_path, db_path):
    other = build_database(tmp_path / "other.db")
    assert other.read_bytes() == db_path.read_bytes()


def test_list_datacenters(client):
    datacenters = client.get("/api/v1/datacenters").json()
    assert len(datacenters) == len(DATACENTERS)
    assert sum(dc["server_count"] for dc in datacenters) == COUNTS["servers"]


def test_datacenter_not_found(client):
    assert client.get("/api/v1/datacenters/999").status_code == 404


def test_servers_pagination(client):
    body = client.get("/api/v1/servers", params={"page": 2, "page_size": 50}).json()
    assert body["total"] == COUNTS["servers"]
    assert body["pages"] == COUNTS["servers"] // 50
    assert len(body["items"]) == 50
    assert body["items"][0]["id"] == 51


@pytest.mark.parametrize(
    ("params", "field", "expected"),
    [
        ({"environment": "production"}, "environment", "production"),
        ({"region": "us-east-1"}, "region", "us-east-1"),
        ({"status": "critical"}, "status", "critical"),
    ],
)
def test_servers_filters(client, params, field, expected):
    items = client.get("/api/v1/servers", params={**params, "page_size": 100}).json()["items"]
    assert items
    assert all(item[field] == expected for item in items)


def test_servers_combined_filters(client):
    items = client.get("/api/v1/servers", params={"region": "us-east-1", "status": "healthy", "page_size": 100}).json()[
        "items"
    ]
    assert all(item["region"] == "us-east-1" and item["status"] == "healthy" for item in items)


def test_servers_search(client):
    items = client.get("/api/v1/servers", params={"search": "db-"}).json()["items"]
    assert items
    assert all("db-" in item["hostname"] for item in items)


def test_servers_sorting(client):
    items = client.get("/api/v1/servers", params={"sort": "cpu_usage", "order": "desc"}).json()["items"]
    usages = [item["cpu_usage"] for item in items]
    assert usages == sorted(usages, reverse=True)


def test_servers_rejects_unknown_sort_column(client):
    """La lista blanca evita inyectar SQL a través del ordenamiento."""
    response = client.get("/api/v1/servers", params={"sort": "id; DROP TABLE servers"})
    assert response.status_code == 422


def test_servers_summary(client):
    summary = client.get("/api/v1/servers/summary").json()
    assert summary["total"] == COUNTS["servers"]
    assert summary["healthy"] + summary["warning"] + summary["critical"] == summary["total"]


def test_servers_summary_with_filter(client):
    production = client.get("/api/v1/servers/summary", params={"environment": "production"}).json()
    listed = client.get("/api/v1/servers", params={"environment": "production"}).json()
    assert production["total"] == listed["total"]


def test_server_detail_and_not_found(client):
    assert client.get("/api/v1/servers/1").json()["id"] == 1
    assert client.get("/api/v1/servers/99999").status_code == 404


def test_incidents_filters(client):
    body = client.get("/api/v1/incidents", params={"severity": "critical", "status": "open"}).json()
    assert body["total"] > 0
    assert all(i["severity"] == "critical" and i["status"] == "open" for i in body["items"])


def test_incidents_default_order_is_most_recent_first(client):
    dates = [i["created_at"] for i in client.get("/api/v1/incidents").json()["items"]]
    assert dates == sorted(dates, reverse=True)


def test_incidents_by_server(client):
    items = client.get("/api/v1/incidents", params={"server_id": 1, "page_size": 100}).json()["items"]
    assert all(i["server_id"] == 1 for i in items)


def test_deployments_filters(client):
    body = client.get("/api/v1/deployments", params={"environment": "production", "status": "failed"}).json()
    assert body["total"] > 0
    assert all(d["environment"] == "production" and d["status"] == "failed" for d in body["items"])


def test_invalid_enum_value_returns_422(client):
    assert client.get("/api/v1/servers", params={"environment": "qa"}).status_code == 422
