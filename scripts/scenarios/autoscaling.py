"""Escenario 4 — Autoescalado horizontal bajo carga.

Un pod de k6 genera carga sostenida dentro del cluster. metrics-server mide el
consumo de CPU y el HPA (objetivo: 70% de la CPU solicitada) añade réplicas
hasta maxReplicas. La reducción posterior respeta la ventana de estabilización
del HPA (5 minutos por defecto) para evitar oscilaciones.
"""

import json
import sys
import time
from pathlib import Path

from common import (
    DEPLOYMENT,
    K6_IMAGE,
    kubectl,
    kubectl_json,
    log,
    print_pods,
    restricted_pod,
    section,
    service_ip,
)

LOAD_SCRIPT = Path(__file__).resolve().parent.parent / "load" / "load-test.js"
POD = "k6-load"
CONFIGMAP = "k6-script"


def hpa_status() -> tuple[int, int, str]:
    hpa = kubectl_json("get", "hpa", DEPLOYMENT)
    metrics = hpa["status"].get("currentMetrics") or [{}]
    cpu = metrics[0].get("resource", {}).get("current", {}).get("averageUtilization")
    return hpa["status"].get("currentReplicas", 0), hpa["status"].get("desiredReplicas", 0), f"{cpu}%"


def start_load() -> None:
    kubectl("delete", "pod", POD, "--ignore-not-found", "--wait=true")
    kubectl("delete", "configmap", CONFIGMAP, "--ignore-not-found")
    kubectl("create", "configmap", CONFIGMAP, f"--from-file=load-test.js={LOAD_SCRIPT}")
    container = {
        "image": K6_IMAGE,
        "args": ["run", "--no-color", "/scripts/load-test.js"],
        "env": [{"name": "TARGET", "value": f"http://{service_ip()}"}],
        "resources": {"requests": {"cpu": "200m", "memory": "128Mi"}, "limits": {"cpu": "1", "memory": "256Mi"}},
        "volumeMounts": [{"name": "script", "mountPath": "/scripts"}, {"name": "tmp", "mountPath": "/tmp"}],
    }
    volumes = [{"name": "script", "configMap": {"name": CONFIGMAP}}, {"name": "tmp", "emptyDir": {}}]
    kubectl("apply", "-f", "-", stdin=json.dumps(restricted_pod(POD, container, uid=12345, volumes=volumes)))


def load_finished() -> bool:
    return kubectl("get", "pod", POD, "-o", "jsonpath={.status.phase}") in ("Succeeded", "Failed")


def main() -> int:
    section("Escenario 4 — Autoescalado bajo carga")
    hpa = kubectl_json("get", "hpa", DEPLOYMENT)["spec"]
    initial, _, cpu = hpa_status()
    log(f"Estado inicial: {initial} réplicas, CPU {cpu} (objetivo {hpa['metrics'][0]['resource']['target']})")

    start_load()
    log("k6: 10 usuarios virtuales durante ~2m45s contra /api/v1/servers")

    section("Evolución del HPA (cada 10s)")
    peak, first_scale = initial, None
    start = time.monotonic()
    while not load_finished():
        current, desired, cpu = hpa_status()
        elapsed = time.monotonic() - start
        log(f"t={elapsed:4.0f}s  CPU={cpu:>5}  réplicas={current} (deseadas={desired})")
        if current > initial and first_scale is None:
            first_scale = elapsed
        peak = max(peak, current)
        time.sleep(10)

    print_pods()
    section("Resumen de k6")
    k6_output = kubectl("logs", POD)
    summary = k6_output[k6_output.find("THRESHOLDS") :] if "THRESHOLDS" in k6_output else k6_output[-2500:]
    print(summary)
    k6_passed = kubectl("get", "pod", POD, "-o", "jsonpath={.status.phase}") == "Succeeded"
    kubectl("delete", "pod", POD, "--wait=false", check=False)
    kubectl("delete", "configmap", CONFIGMAP, check=False)

    log("La reducción a minReplicas ocurrirá tras la ventana de estabilización del HPA (~5 min).")
    checks = {
        f"el HPA escaló por encima de {initial} réplicas": peak > initial,
        f"alcanzó maxReplicas ({hpa['maxReplicas']})": peak == hpa["maxReplicas"],
        "umbrales de k6 cumplidos (errores < 1%, p95 < 1s)": k6_passed,
    }
    section("Resultado")
    if first_scale is not None:
        print(f"  Primer escalado a los {first_scale:.0f}s de iniciar la carga; pico de {peak} réplicas")
    for name, ok in checks.items():
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
