"""Escenario 3 — Despliegue defectuoso y rollback.

Se publica una revisión cuyo readiness probe nunca pasa
(SIMULATE_READINESS_FAILURE=true). Con maxUnavailable: 0, Kubernetes no retira
ningún pod sano: el rollout se queda atascado, las réplicas anteriores siguen
sirviendo y, al superar progressDeadlineSeconds, el Deployment se marca como
fallido. Después se revierte con "kubectl rollout undo".
"""

import sys
import time

from common import DEPLOYMENT, TrafficProbe, kubectl, kubectl_json, log, print_pods, section, wait_for


def condition(reason_type: str) -> dict:
    conditions = kubectl_json("get", "deployment", DEPLOYMENT)["status"].get("conditions", [])
    return next((c for c in conditions if c["type"] == reason_type), {})


def replica_sets() -> None:
    print(kubectl("get", "rs", "-l", "app.kubernetes.io/name=observability-api"))


def main() -> int:
    section("Escenario 3 — Despliegue defectuoso y rollback")
    revision_before = kubectl_json("get", "deployment", DEPLOYMENT)["metadata"]["annotations"][
        "deployment.kubernetes.io/revision"
    ]
    log(f"Revisión sana actual: {revision_before}")

    with TrafficProbe() as probe:
        time.sleep(5)

        section("Despliegue de la revisión defectuosa")
        kubectl("set", "env", f"deployment/{DEPLOYMENT}", "SIMULATE_READINESS_FAILURE=true")
        log("Nueva revisión publicada: su readiness probe devolverá 503")
        time.sleep(20)
        replica_sets()
        print_pods()

        log("Esperando a que venza progressDeadlineSeconds (120s)...")
        waited = wait_for(
            lambda: condition("Progressing").get("reason") == "ProgressDeadlineExceeded", timeout=240, interval=5
        )
        progressing = condition("Progressing")
        log(f"Rollout marcado como fallido tras {waited:.0f}s: {progressing['reason']} — {progressing['message']}")

        section("Historial y rollback")
        print(kubectl("rollout", "history", f"deployment/{DEPLOYMENT}"))
        log(f"kubectl rollout undo (vuelve a la revisión {revision_before})")
        kubectl("rollout", "undo", f"deployment/{DEPLOYMENT}")
        kubectl("rollout", "status", f"deployment/{DEPLOYMENT}", "--timeout=180s")
        log("Rollback completado")
        replica_sets()
        print_pods()

        time.sleep(5)
        availability = probe.report()

    env = kubectl_json("get", "deployment", DEPLOYMENT)["spec"]["template"]["spec"]["containers"][0].get("env", [])
    checks = {
        "el rollout defectuoso se detectó (ProgressDeadlineExceeded)": progressing.get("reason")
        == "ProgressDeadlineExceeded",
        "la plantilla vuelve a la configuración sana": not any(e["name"] == "SIMULATE_READINESS_FAILURE" for e in env),
        "disponibilidad 100% durante todo el incidente": availability == 100,
    }
    section("Resultado")
    for name, ok in checks.items():
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
