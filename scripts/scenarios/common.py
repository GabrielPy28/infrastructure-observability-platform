"""Utilidades compartidas por los escenarios de resiliencia.

Los escenarios se ejecutan contra el entorno prod del cluster local (el que
tiene alta disponibilidad: HPA 2-4 réplicas). La disponibilidad se mide desde
DENTRO del cluster con un pod cliente: un port-forward se conecta a un único
pod y no reflejaría lo que ve un consumidor real del Service.
"""

import json
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone

CONTEXT = "kind-devops-platform"
NAMESPACE = "observability-prod"
DEPLOYMENT = "observability-api"
SELECTOR = "app.kubernetes.io/name=observability-api"

CURL_IMAGE = "curlimages/curl:8.22.0"
K6_IMAGE = "grafana/k6:2.3.0"

# kubectl y k6 emiten UTF-8; en Windows la consola usa otra codificación por defecto.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(message: str) -> None:
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] {message}", flush=True)


def section(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


TRANSIENT_ERRORS = ("Unable to connect to the server", "TLS handshake timeout", "connection refused")


def kubectl(*args: str, stdin: str | None = None, check: bool = True, namespaced: bool = True) -> str:
    """Ejecuta kubectl. Reintenta los errores de conexión transitorios: bajo carga
    intensa, el API server de un cluster local puede tardar en responder."""
    namespace = ["-n", NAMESPACE] if namespaced else []
    for attempt in range(1, 6):
        result = subprocess.run(
            ["kubectl", "--context", CONTEXT, "--request-timeout=20s", *namespace, *args],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode == 0 or not any(error in result.stderr for error in TRANSIENT_ERRORS):
            break
        log(f"API server no disponible (intento {attempt}/5), reintentando...")
        time.sleep(5 * attempt)
    if check and result.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)} falló:\n{result.stderr}")
    return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()


def kubectl_json(*args: str) -> dict:
    return json.loads(kubectl(*args, "-o", "json"))


def wait_for(condition: Callable[[], bool], timeout: float, interval: float = 2) -> float:
    """Espera a que se cumpla la condición; devuelve los segundos transcurridos."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if condition():
            return time.monotonic() - start
        time.sleep(interval)
    raise TimeoutError(f"La condición no se cumplió en {timeout}s")


def service_ip() -> str:
    # IP del Service en vez de su nombre DNS: los escenarios que desalojan
    # nodos pueden mover CoreDNS y no queremos medir fallos de DNS.
    return kubectl("get", "svc", DEPLOYMENT, "-o", "jsonpath={.spec.clusterIP}")


def app_pods() -> list[dict]:
    return kubectl_json("get", "pods", "-l", SELECTOR)["items"]


def is_ready(pod: dict) -> bool:
    if pod["metadata"].get("deletionTimestamp"):
        return False
    conditions = pod.get("status", {}).get("conditions", [])
    return any(c["type"] == "Ready" and c["status"] == "True" for c in conditions)


def ready_pods() -> list[dict]:
    return [pod for pod in app_pods() if is_ready(pod)]


def print_pods() -> None:
    print(kubectl("get", "pods", "-l", SELECTOR, "-o", "wide"))


def restricted_pod(name: str, container: dict, uid: int, volumes: list | None = None) -> dict:
    """Pod auxiliar que cumple Pod Security "restricted" (lo exige el namespace)."""
    container = {
        **container,
        "name": name,
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
            "readOnlyRootFilesystem": True,
        },
        # La API key llega del Secret que crea Terraform, igual que en la app.
        "envFrom": [{"secretRef": {"name": "observability-api-secrets"}}],
    }
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": name, "labels": {"app.kubernetes.io/component": "resilience-scenario"}},
        "spec": {
            "restartPolicy": "Never",
            "automountServiceAccountToken": False,
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": uid,
                "runAsGroup": uid,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [container],
            "volumes": volumes or [],
        },
    }


class TrafficProbe:
    """Pod cliente que consulta el Service 4 veces por segundo y registra cada respuesta."""

    NAME = "traffic-probe"

    def __enter__(self) -> "TrafficProbe":
        kubectl("delete", "pod", self.NAME, "--ignore-not-found", "--wait=true")
        url = f"http://{service_ip()}/api/v1/servers/summary"
        script = (
            "while true; do "
            'code=$(curl -s -o /dev/null -m 2 -w "%{http_code}" -H "X-API-Key: $API_KEY" ' + url + "); "
            'echo "$(date -u +%H:%M:%S) $code"; sleep 0.25; done'
        )
        pod = restricted_pod(self.NAME, {"image": CURL_IMAGE, "command": ["sh", "-c", script]}, uid=100)
        kubectl("apply", "-f", "-", stdin=json.dumps(pod))
        kubectl("wait", "--for=condition=Ready", f"pod/{self.NAME}", "--timeout=90s")
        log(f"Cliente de tráfico activo -> GET {url} (4 peticiones/s)")
        return self

    def responses(self) -> list[tuple[str, str]]:
        lines = kubectl("logs", self.NAME).splitlines()
        return [tuple(line.split()) for line in lines if len(line.split()) == 2]

    def report(self) -> float:
        responses = self.responses()
        codes = Counter(code for _, code in responses)
        total = len(responses)
        ok = codes.get("200", 0)
        availability = 100 * ok / total if total else 0.0
        errors = [f"{moment} -> {code}" for moment, code in responses if code != "200"]
        section("Disponibilidad medida por el cliente")
        print(f"Peticiones: {total} | códigos: {dict(codes)} | disponibilidad: {availability:.2f}%")
        if errors:
            print("Respuestas fallidas:", ", ".join(errors[:10]), "..." if len(errors) > 10 else "")
        return availability

    def __exit__(self, *exc) -> None:
        kubectl("delete", "pod", self.NAME, "--ignore-not-found", "--wait=false", check=False)
