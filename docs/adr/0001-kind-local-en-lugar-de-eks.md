# ADR 0001 — Kind local en lugar de EKS

- **Estado:** Aceptada
- **Fecha:** 2026-09-28

## Contexto

El objetivo del proyecto es levantar el ciclo completo de una plataforma: Infrastructure
as Code, Kubernetes, CI/CD y resiliencia. El producto es la plataforma, no la
aplicación en sí. Un cluster gestionado en la nube (EKS) es lo que se usa en producción,
pero tiene tres inconvenientes para este proyecto:

- **Coste continuo:** unos 170 USD/mes por control plane, nodos y NAT gateway.
- **Tiempo:** IAM, networking, node groups y permisos pueden ocupar buena parte del
  proyecto en troubleshooting de AWS en vez de en la plataforma.
- **Reproducibilidad:** nadie que clone el repositorio podría ejecutarlo sin una
  cuenta de AWS.

## Decisión

- El entorno de ejecución es **Kind** (Kubernetes in Docker) con 1 control-plane y
  2 workers, creado por Terraform (`terraform/cluster`).
- La migración a la nube se documenta con un **módulo de EKS real**
  (`terraform/aws/eks`) que el CI valida en cada PR (`fmt`, `validate`, tflint,
  Trivy), pero que nunca se aplica.
- La plataforma se diseña para que **solo la capa de cluster cambie** al pasar a EKS:
  el módulo `platform`, los manifiestos de Kustomize y la imagen se reutilizan
  tal cual.

## Consecuencias

**Positivas**

- Coste cero, y cualquiera puede reproducir la plataforma con `task tf:up`.
- El pipeline de CD crea un cluster efímero idéntico en cada merge (ver
  [ADR 0005](0005-cicd-mismas-tareas-y-cluster-efimero.md)).
- La separación entre la capa de cluster y la de plataforma queda demostrada en el
  código, no solo descrita.

**Negativas / trade-offs**

- Hay piezas de la nube que no se ejercitan: load balancers, IAM de los pods y
  autoscaling de nodos.
- metrics-server necesita `--kubelet-insecure-tls`, algo aceptable solo en local.
- La imagen de nodo debe coincidir con la versión de kind que incluye el provider
  `tehcyx/kind` (v0.31.0 → Kubernetes 1.35), y por eso está fijada por digest.

## Alternativas consideradas

- **EKS real:** descartado por coste y tiempo. Se mantiene como módulo validado.
- **Cluster de Kubernetes de Docker Desktop:** lo gestiona la interfaz gráfica de
  Docker Desktop, así que Terraform no puede crearlo ni destruirlo y no es
  reproducible en CI.
- **minikube / k3d:** válidos, pero Kind es el estándar para probar Kubernetes en
  CI y tiene provider de Terraform.
