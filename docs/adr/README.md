# Architecture Decision Records

Decisiones de arquitectura del proyecto: el contexto, la decisión, sus consecuencias
y las alternativas descartadas.

| ADR | Decisión |
|---|---|
| [0001](0001-kind-local-en-lugar-de-eks.md) | Kind local en lugar de EKS, con un módulo de EKS validado |
| [0002](0002-sqlite-de-solo-lectura-en-la-imagen.md) | SQLite de solo lectura empaquetado en la imagen |
| [0003](0003-frontera-terraform-kustomize.md) | Frontera entre Terraform (plataforma) y Kustomize (aplicación) |
| [0004](0004-state-de-terraform-por-capas.md) | State de Terraform por capas y por entorno |
| [0005](0005-cicd-mismas-tareas-y-cluster-efimero.md) | CI/CD con las mismas tareas que en local y E2E en un cluster efímero |
| [0006](0006-despliegues-sin-downtime.md) | Estrategia de despliegue sin downtime |
| [0007](0007-seguridad-de-la-cadena-de-suministro.md) | Seguridad de la cadena de suministro y del runtime |
