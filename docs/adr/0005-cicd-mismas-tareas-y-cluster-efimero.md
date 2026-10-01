# ADR 0005 — CI/CD con las mismas tareas que en local y E2E en un cluster efímero

- **Estado:** Aceptada
- **Fecha:** 2026-09-30

## Contexto

El cluster de desarrollo es local (Kind), y un runner de GitHub Actions no puede
alcanzarlo. Además, cuando un pipeline tiene lógica propia (scripts inline,
comandos distintos de los que usa el desarrollador), con el tiempo diverge del
flujo local y aparecen fallos que solo ocurren en CI o solo en local.

## Decisión

- **Taskfile como única interfaz.** El pipeline no tiene lógica de despliegue
  propia: ejecuta `task tf:up`, `task k8s:apply` y `task k8s:smoke`, igual que el
  desarrollador. `IMAGE` y `TAG` se pueden sobrescribir para usar la imagen de GHCR.
- **CI** (`ci.yml`, en cada PR): cinco jobs en paralelo y todos son required status
  checks:
  - lint y tests de la app;
  - hadolint, build y Trivy de la imagen;
  - Terraform (`fmt`, `validate`, tflint);
  - kubeconform;
  - Trivy de la configuración (IaC).
- **CD** (`cd.yml`, en cada merge a `main`):
  1. build → Trivy como security gate → push a GHCR con el tag `<sha>`;
  2. E2E: el runner **descarga la imagen publicada** (no la reconstruye), crea un
     cluster Kind efímero con Terraform, despliega en dev → smoke test → prod →
     smoke test, y destruye la plataforma.
- **El smoke test verifica la versión desplegada:** `/readyz` debe devolver el mismo
  SHA que la imagen.
- **Rollback automático:** si `kubectl rollout status` falla, `task k8s:apply`
  ejecuta `rollout undo` y termina con error.

## Consecuencias

**Positivas**

- Lo que funciona en local funciona en el CD, porque son los mismos comandos.
- Cada merge valida la plataforma completa, Terraform incluido, en unos 4 minutos y
  sin infraestructura permanente.
- **Trazabilidad:** commit → imagen `<sha>` → pod que responde con ese `<sha>`.

**Negativas / trade-offs**

- El cluster efímero valida, pero no hay un entorno persistente desplegado al que
  acceder desde fuera.
- La promoción dev → prod ocurre en el mismo job y sin aprobación manual. En un
  entorno persistente se usaría un GitHub Environment con reviewers.
- Los build con cambios sin commitear necesitan un tag distinto por contenido
  (`<sha>-dirty-<hash>`). Sin él, una corrección no llegaba a desplegarse (ver
  [docs/scenarios.md](../scenarios.md)).

## Alternativas consideradas

- **Self-hosted runner en la máquina local:** frágil y arriesgado en un repositorio
  público, porque ejecutaría código de PRs en el equipo del desarrollador.
- **ArgoCD (GitOps pull-based):** buena opción para un cluster persistente; queda
  fuera del alcance como mejora futura.
- **`helm/kind-action` para crear el cluster:** más rápido, pero no ejercitaría las
  capas de Terraform.
