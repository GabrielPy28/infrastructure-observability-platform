# ADR 0004 — State de Terraform por capas y por entorno

- **Estado:** Aceptada
- **Fecha:** 2026-09-29

## Contexto

La plataforma tiene recursos con ciclos de vida y alcances distintos:

- el **cluster**, que existe una vez;
- los **add-ons de todo el cluster** (metrics-server), compartidos por todos los
  entornos;
- los **recursos por entorno** (namespace, quota, secret), uno por `dev` y otro por
  `prod`.

Con un único root module y un solo state:

- un `apply` en dev podría modificar prod;
- los providers `kubernetes` y `helm` se configurarían con datos de un cluster que
  se crea en ese mismo `apply`, una dependencia frágil que suele fallar en el
  primer `plan` o al recrear el cluster.

## Decisión

Cuatro root modules, cada uno con su propio state, que se aplican en orden:

```text
terraform/cluster  ->  terraform/addons  ->  terraform/envs/dev
                                         ->  terraform/envs/prod
```

- `envs/dev` y `envs/prod` instancian el mismo módulo (`modules/platform`) con
  quotas distintas.
- `addons/` existe porque metrics-server es de todo el cluster: no pertenece a
  ningún entorno, y si lo instalaran los dos, entrarían en conflicto.
- Las capas superiores se conectan al cluster mediante el **kubeconfig**
  (`config_context`), no leyendo atributos de un recurso del mismo `apply`.
- `task tf:up` y `task tf:down` aplican y destruyen las capas en orden e inverso.
- Los `.terraform.lock.hcl` se versionan con checksums de Linux, Windows y macOS.

## Consecuencias

**Positivas**

- **Blast radius acotado:** un error en `envs/dev` no puede tocar prod ni el cluster.
- Los providers siempre se configuran contra un cluster que ya existe.
- El mismo patrón sirve en EKS: solo cambia `kube_context` (ver
  [ADR 0001](0001-kind-local-en-lugar-de-eks.md)).

**Negativas / trade-offs**

- Hay más directorios y más `init`; el Taskfile oculta esa complejidad.
- Las dependencias entre capas son implícitas (orden de aplicación y nombre del
  contexto) y no las detecta `terraform plan`.
- El state es **local**, sin bloqueo ni cifrado. Es aceptable para una sola persona
  en local; en la nube iría en S3 con `use_lockfile` (ya configurado en
  `terraform/aws/eks`).

## Alternativas consideradas

- **Un único root module:** más simple, pero mezcla blast radius y tiene el problema
  del provider configurado en el mismo `apply`.
- **Terraform workspaces para dev y prod:** comparten código y backend, y es fácil
  aplicar en el workspace equivocado. Los directorios separados lo hacen explícito.
- **Terragrunt:** resolvería las dependencias entre capas, pero añade una
  herramienta más para un caso con solo cuatro capas.
