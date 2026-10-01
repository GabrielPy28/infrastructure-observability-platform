"""Escenario 2 — Fallo de un pod y mantenimiento de un nodo.

2a. Se elimina un pod de forma abrupta: el ReplicaSet crea otro y el Service
    solo envía tráfico a pods Ready.
2b. Se drena (drain) el nodo de una réplica, como en un mantenimiento: el
    PodDisruptionBudget limita los desalojos simultáneos y la réplica se
    reprograma en otro nodo.
2c. Tras liberar el nodo, un rollout restart vuelve a repartir las réplicas.

En todos los casos el cliente no debería ver errores.
"""

import sys
import time

from common import (
    DEPLOYMENT,
    TrafficProbe,
    app_pods,
    kubectl,
    log,
    print_pods,
    ready_pods,
    section,
    wait_for,
)


def main() -> int:
    replicas = len(ready_pods())
    section(f"Escenario 2 — Fallo de pod y mantenimiento de nodo ({replicas} réplicas)")
    print_pods()

    with TrafficProbe() as probe:
        time.sleep(5)

        section("2a. Eliminación abrupta de un pod")
        victim = ready_pods()[0]["metadata"]["name"]
        log(f"Eliminando {victim}")
        kubectl("delete", "pod", victim, "--wait=false")
        recovery = wait_for(
            lambda: len([p for p in ready_pods() if p["metadata"]["name"] != victim]) >= replicas, timeout=120
        )
        log(f"Réplicas Ready restablecidas en {recovery:.1f}s")
        print_pods()

        section("2b. Drain del nodo de una réplica (mantenimiento)")
        node = ready_pods()[0]["spec"]["nodeName"]
        log(f"Drenando {node} (el PDB permite desalojar como máximo 1 réplica a la vez)")
        try:
            kubectl(
                "drain",
                node,
                "--ignore-daemonsets",
                "--delete-emptydir-data",
                # El pod cliente no tiene controlador y drain se negaría a
                # desalojarlo; además debe seguir midiendo durante el drain.
                "--pod-selector=app.kubernetes.io/component!=resilience-scenario",
                "--timeout=180s",
                namespaced=False,
            )
            wait_for(lambda: len(ready_pods()) >= replicas, timeout=120)
            moved = {p["metadata"]["name"]: p["spec"]["nodeName"] for p in app_pods()}
            log(f"Réplicas tras el drain: {moved}")
        finally:
            # El nodo siempre vuelve a aceptar pods, aunque el drain falle.
            kubectl("uncordon", node, namespaced=False)
            log(f"{node} vuelve a aceptar pods (uncordon)")

        section("2c. Reequilibrio tras el mantenimiento (rollout restart)")
        # Kubernetes no mueve pods en ejecución al liberar un nodo; un reinicio
        # progresivo los reprograma respetando el topologySpreadConstraint.
        kubectl("rollout", "restart", f"deployment/{DEPLOYMENT}")
        kubectl("rollout", "status", f"deployment/{DEPLOYMENT}", "--timeout=180s")
        balanced = {p["spec"]["nodeName"] for p in ready_pods()}
        log(f"Réplicas repartidas en: {', '.join(sorted(balanced))}")

        time.sleep(5)
        availability = probe.report()

    checks = {
        "pod recreado en menos de 60s": recovery < 60,
        "ninguna réplica queda en el nodo drenado": node not in moved.values(),
        "réplicas repartidas entre nodos tras el reequilibrio": len(balanced) > 1,
        "disponibilidad 100%": availability == 100,
    }
    section("Resultado")
    for name, ok in checks.items():
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
