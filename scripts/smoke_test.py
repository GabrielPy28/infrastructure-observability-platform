"""Smoke test post-despliegue contra un entorno del cluster.

Abre un port-forward al Service, obtiene la API key del state de Terraform y
verifica que la versión desplegada responde como se espera. Sale con código 1
si alguna comprobación falla, para que el pipeline de CD se detenga.

Uso:
    python scripts/smoke_test.py --env dev --expected-version 1a2b3c4
"""

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_ENV = {"dev": "development", "prod": "production"}
EXPECTED_SERVERS = 500


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def get(url: str, api_key: str | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers={"X-API-Key": api_key} if api_key else {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def terraform_api_key(env: str) -> str:
    return subprocess.run(
        ["terraform", f"-chdir={ROOT / 'terraform' / 'envs' / env}", "output", "-raw", "api_key"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def wait_until_reachable(base_url: str, attempts: int = 30) -> None:
    for _ in range(attempts):
        try:
            get(f"{base_url}/healthz")
            return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(1)
    raise RuntimeError("El port-forward no respondió a tiempo")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", choices=APP_ENV, required=True)
    parser.add_argument("--context", default="kind-devops-platform")
    parser.add_argument("--expected-version", help="SHA de la imagen que debería estar desplegada")
    args = parser.parse_args()

    namespace = f"observability-{args.env}"
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    api_key = terraform_api_key(args.env)

    port_forward = subprocess.Popen(
        ["kubectl", "--context", args.context, "-n", namespace, "port-forward", "svc/observability-api", f"{port}:80"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    results: list[tuple[str, bool]] = []
    try:
        wait_until_reachable(base_url)

        status, body = get(f"{base_url}/readyz")
        results.append(("GET /readyz -> 200 ready", status == 200 and body.get("status") == "ready"))
        results.append((f"APP_ENV = {APP_ENV[args.env]}", body.get("environment") == APP_ENV[args.env]))
        if args.expected_version:
            results.append(
                (f"versión desplegada = {args.expected_version}", body.get("version") == args.expected_version)
            )

        status, _ = get(f"{base_url}/api/v1/servers/summary")
        results.append(("sin API key -> 401", status == 401))

        status, body = get(f"{base_url}/api/v1/servers/summary", api_key)
        results.append(
            (
                f"con API key -> 200 y {EXPECTED_SERVERS} servidores",
                status == 200 and body.get("total") == EXPECTED_SERVERS,
            )
        )

        status, body = get(f"{base_url}/api/v1/incidents?severity=critical&page_size=5", api_key)
        results.append(("filtros de incidentes", status == 200 and len(body.get("items", [])) == 5))
    finally:
        port_forward.terminate()
        port_forward.wait(timeout=10)

    print(f"Smoke test — entorno {args.env} ({namespace})")
    for name, ok in results:
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")
    failed = [name for name, ok in results if not ok]
    print(f"Resultado: {len(results) - len(failed)}/{len(results)} comprobaciones correctas")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
