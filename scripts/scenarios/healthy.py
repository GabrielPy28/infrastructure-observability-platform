"""Escenario 1 — Despliegue sano.

Verifica que prod corre con las réplicas mínimas del HPA, repartidas entre
nodos, y que el Service responde de forma continua.
"""

import sys
import time

from common import DEPLOYMENT, TrafficProbe, kubectl_json, log, print_pods, ready_pods, section


def main() -> int:
    section("Escenario 1 — Despliegue sano")
    hpa = kubectl_json("get", "hpa", DEPLOYMENT)
    deployment = kubectl_json("get", "deployment", DEPLOYMENT)
    image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]
    pods = ready_pods()
    nodes = {pod["spec"]["nodeName"] for pod in pods}

    log(f"Imagen desplegada: {image}")
    log(f"Réplicas Ready: {len(pods)} (HPA min={hpa['spec']['minReplicas']}, max={hpa['spec']['maxReplicas']})")
    log(f"Nodos con réplicas: {len(nodes)} -> {', '.join(sorted(nodes))}")
    print_pods()

    with TrafficProbe() as probe:
        time.sleep(15)
        availability = probe.report()

    checks = {
        "réplicas >= minReplicas": len(pods) >= hpa["spec"]["minReplicas"],
        "réplicas en más de un nodo": len(nodes) > 1,
        "disponibilidad 100%": availability == 100,
    }
    section("Resultado")
    for name, ok in checks.items():
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
