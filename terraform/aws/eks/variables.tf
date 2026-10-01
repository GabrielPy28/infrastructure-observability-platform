variable "region" {
  description = "Región de AWS."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Nombre del cluster EKS (mismo nombre que el cluster Kind local)."
  type        = string
  default     = "devops-platform"
}

variable "kubernetes_version" {
  description = "Versión de Kubernetes; la misma que valida el CI (kubeconform) y usa Kind."
  type        = string
  default     = "1.35"
}

variable "vpc_cidr" {
  description = "Rango de direcciones de la VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "node_instance_types" {
  description = "Tipos de instancia de los nodos gestionados."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_scaling" {
  description = "Tamaño del node group (equivalente a los 2 workers de Kind)."
  type = object({
    min     = number
    max     = number
    desired = number
  })
  default = {
    min     = 2
    max     = 4
    desired = 2
  }
}

variable "github_repository" {
  description = "Repositorio (owner/name) cuyo pipeline de CD puede desplegar en el cluster."
  type        = string
  default     = "GabrielPy28/infrastructure-observability-platform"
}

variable "app_namespaces" {
  description = "Namespaces de la aplicación (los crea terraform/modules/platform)."
  type        = list(string)
  default     = ["observability-dev", "observability-prod"]
}
