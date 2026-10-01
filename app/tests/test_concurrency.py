from concurrent.futures import ThreadPoolExecutor


def test_concurrent_requests_do_not_fail(client):
    """Regresión: bajo carga concurrente, FastAPI puede abrir la conexión en un
    hilo y usarla en otro; sqlite3 lo rechaza si check_same_thread=True (500)."""

    def request(_):
        return client.get("/api/v1/servers", params={"page_size": 100}).status_code

    with ThreadPoolExecutor(max_workers=30) as pool:
        codes = list(pool.map(request, range(300)))

    assert codes.count(200) == len(codes), f"códigos distintos de 200: {set(codes) - {200}}"
