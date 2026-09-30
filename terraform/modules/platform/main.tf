# Plataforma de un entorno: todo lo que la aplicación necesita que exista
# antes de desplegarse. Los objetos de la aplicación (Deployment, Service,
# HPA...) NO se gestionan aquí: pertenecen a Kustomize (k8s/).

locals {
  namespace = "${var.app_name}-${var.environment}"

  labels = {
    "app.kubernetes.io/part-of"    = "infrastructure-observability-platform"
    "app.kubernetes.io/managed-by" = "terraform"
    "environment"                  = var.environment
  }
}

resource "kubernetes_namespace_v1" "this" {
  metadata {
    name = local.namespace

    labels = merge(local.labels, {
      # Pod Security Admission: se rechaza cualquier pod que no cumpla el
      # perfil "restricted" (root, privilegios, capabilities, seccomp...).
      "pod-security.kubernetes.io/enforce" = "restricted"
      "pod-security.kubernetes.io/warn"    = "restricted"
      "pod-security.kubernetes.io/audit"   = "restricted"
    })
  }
}

# Techo de recursos del entorno: un despliegue descontrolado no puede
# consumir todo el cluster.
resource "kubernetes_resource_quota_v1" "compute" {
  metadata {
    name      = "compute-quota"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  spec {
    hard = {
      "requests.cpu"    = var.quota.requests_cpu
      "requests.memory" = var.quota.requests_memory
      "limits.cpu"      = var.quota.limits_cpu
      "limits.memory"   = var.quota.limits_memory
      "pods"            = var.quota.pods
    }
  }
}

# Con una ResourceQuota activa, un pod sin requests/limits sería rechazado;
# el LimitRange les asigna valores por defecto.
resource "kubernetes_limit_range_v1" "defaults" {
  metadata {
    name      = "container-defaults"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  spec {
    limit {
      type = "Container"
      default_request = {
        cpu    = var.container_defaults.request_cpu
        memory = var.container_defaults.request_memory
      }
      default = {
        cpu    = var.container_defaults.limit_cpu
        memory = var.container_defaults.limit_memory
      }
    }
  }
}

# La API key se genera mediante Terraform y nunca se almacena en el repositorio.
# Nota: aunque se marque como sensitive, el valor puede quedar registrado
# en el Terraform state. En un entorno real, el state debe almacenarse en
# un backend seguro, cifrado y con acceso restringido.
resource "random_password" "api_key" {
  length  = 40
  special = false
}

resource "kubernetes_secret_v1" "api" {
  metadata {
    name      = "${var.app_name}-api-secrets"
    namespace = kubernetes_namespace_v1.this.metadata[0].name
    labels    = local.labels
  }

  data = {
    API_KEY = random_password.api_key.result
  }
}
