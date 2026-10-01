# ADR 0006 — Estrategia de despliegue sin downtime

- **Estado:** Aceptada
- **Fecha:** 2026-09-30

## Contexto

La plataforma debe mantener el servicio disponible ante despliegues defectuosos,
fallos de pods, mantenimiento de nodos y picos de carga. Los escenarios de
resiliencia ([docs/scenarios.md](../scenarios.md)) miden la disponibilidad desde
dentro del cluster y detectaron varios fallos que la configuración inicial no
cubría.

## Decisión

Configuración del Deployment ([k8s/base/deployment.yaml](../../k8s/base/deployment.yaml)):

| Mecanismo | Configuración | Qué evita |
|---|---|---|
| Rolling update conservador | `maxUnavailable: 0`, `maxSurge: 1` | Que una versión rota sustituya pods sanos |
| Detección de rollouts atascados | `progressDeadlineSeconds: 120` | Esperar indefinidamente a una versión que nunca estará Ready |
| Probes separados | readiness `/readyz` (comprueba la BD), liveness `/healthz` (no la comprueba) | Enviar tráfico a pods no preparados y reinicios en cascada si falla una dependencia |
| Apagado ordenado | `preStop: sleep 5s` | Conexiones nuevas a un pod que ya recibió `SIGTERM` mientras kube-proxy actualiza las reglas |
| Reparto entre nodos | `topologySpreadConstraints` con `matchLabelKeys: [pod-template-hash]` | Que la caída de un nodo deje el servicio sin réplicas |
| Disrupciones voluntarias | PodDisruptionBudget `maxUnavailable: 1` | Que un drain desaloje todas las réplicas a la vez |
| Escalado | HPA al 70 % de la CPU solicitada; el Deployment **no** declara `replicas` | Que `kubectl apply` resetee lo que escaló el HPA |
| Configuración | `configMapGenerator` (nombre con hash) | Que cambiar la configuración no reinicie los pods |

## Consecuencias

**Positivas**

- **Verificado con 14.006 peticiones y 0 errores** a lo largo de cuatro escenarios:
  pod eliminado, drain de nodo, versión defectuosa con rollback y carga con
  autoescalado.
- Una versión defectuosa nunca recibe tráfico: el rollout se detiene y la versión
  anterior sigue sirviendo hasta el rollback.

**Negativas / trade-offs**

- Los despliegues son más lentos: un pod nuevo a la vez, más `minReadySeconds` y
  el `preStop`.
- `maxSurge: 1` requiere capacidad extra en el cluster y margen en la ResourceQuota
  (las quotas de Terraform incluyen ese pod adicional).
- `topologySpreadConstraints` solo actúa al programar pods. Después de un drain hace
  falta un `rollout restart` (o un descheduler) para volver a repartir.
- El HPA reduce réplicas tras una ventana de estabilización de 5 minutos: es más
  estable, pero consume más recursos después de un pico.

## Alternativas consideradas

- **Blue/green o canary (Argo Rollouts, service mesh):** permiten análisis
  automático y rollback por métricas, pero requieren herramientas fuera del alcance
  del proyecto.
- **`minAvailable: 1` en el PDB:** bloquearía los drains en el entorno dev, que
  tiene una sola réplica.
- **`whenUnsatisfiable: DoNotSchedule`:** garantiza el reparto, pero durante un
  drain con un solo nodo disponible dejaría réplicas en `Pending`.
