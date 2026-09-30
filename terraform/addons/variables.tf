variable "kubeconfig_path" {
  type    = string
  default = "~/.kube/config"
}

variable "kube_context" {
  description = "Contexto del cluster creado por la capa cluster/."
  type        = string
  default     = "kind-devops-platform"
}

variable "metrics_server_chart_version" {
  type    = string
  default = "3.14.0"
}
