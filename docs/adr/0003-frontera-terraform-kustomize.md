# ADR 0003 — Frontera entre Terraform y Kustomize

- **Estado:** Aceptada
- **Fecha:** 2026-09-28

## Contexto

Terraform puede gestionar cualquier objeto de Kubernetes, incluidos Deployments y
Services. Si Terraform y `kubectl` gestionan el mismo objeto, aparece **drift**: un
`kubectl rollout undo` revierte el Deployment, y el siguiente `terraform apply`
deshace ese rollback. Cada objeto necesita un único dueño.

Además, el ciclo de vida es distinto en cada caso: la plataforma cambia poco y de
forma controlada, mientras que la aplicación se despliega en cada merge.

## Decisión

| Dueño | Gestiona | Ubicación |
|---|---|---|
| **Terraform** | Cluster, add-ons, namespaces (con Pod Security), ResourceQuota, LimitRange, Secret con la API key | `terraform/` |
| **Kustomize** | Deployment, Service, HPA, PodDisruptionBudget, ConfigMap | `k8s/` |

- Los namespaces **no** aparecen en Kustomize.
- `task k8s:apply` falla con un mensaje claro si el namespace no existe, porque la
  plataforma debe existir antes que la aplicación.
- El Deployment carga el Secret creado por Terraform con `secretRef`. Si la
  plataforma no existe, el pod no arranca.

## Consecuencias

**Positivas**

- **Sin drift:** después de desplegar la aplicación, `terraform plan` no muestra
  cambios en ninguna capa (verificado en la Fase 3).
- Los rollbacks de la aplicación (`kubectl rollout undo`, rollback automático del
  CD) no entran en conflicto con Terraform.
- Cada herramienta hace lo que mejor sabe hacer: Terraform gestiona recursos de
  larga vida con state, y Kustomize gestiona manifiestos declarativos por entorno.

**Negativas / trade-offs**

- Hay dos herramientas y dos flujos de trabajo, y el orden importa: primero
  `task tf:up`, después `task k8s:deploy`.
- La API key vive en el state de Terraform en texto plano. En la nube, el state iría
  en un backend cifrado o el secret pasaría a AWS Secrets Manager (ver
  [terraform/aws/README.md](../../terraform/aws/README.md)).

## Alternativas consideradas

- **Todo en Terraform** (`kubernetes_deployment_v1`): el rollback pasaría a
  depender de cambiar variables y aplicar Terraform, y `kubectl rollout` provocaría
  drift.
- **Todo en Kustomize/kubectl:** el cluster y los add-ons quedarían fuera del
  Infrastructure as Code, y sin state no habría plan ni detección de drift.
- **Helm para la aplicación:** válido, pero las plantillas no aportan nada con dos
  entornos simples; los overlays de Kustomize son suficientes y no necesitan
  herramientas extra (`kubectl apply -k`).
