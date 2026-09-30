variable "environment" {
  description = "Nombre corto del entorno."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment debe ser dev o prod."
  }
}

variable "app_name" {
  description = "Nombre de la aplicación; prefijo del namespace y del Secret."
  type        = string
  default     = "observability"
}

variable "quota" {
  description = "Límite total de recursos del namespace (ResourceQuota)."
  type = object({
    requests_cpu    = string
    requests_memory = string
    limits_cpu      = string
    limits_memory   = string
    pods            = number
  })
}

variable "container_defaults" {
  description = "Recursos por defecto para contenedores que no los declaren (LimitRange)."
  type = object({
    request_cpu    = string
    request_memory = string
    limit_cpu      = string
    limit_memory   = string
  })
  default = {
    request_cpu    = "50m"
    request_memory = "64Mi"
    limit_cpu      = "200m"
    limit_memory   = "128Mi"
  }
}
