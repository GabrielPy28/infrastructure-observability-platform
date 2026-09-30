variable "kubeconfig_path" {
  type    = string
  default = "~/.kube/config"
}

variable "kube_context" {
  description = "Contexto del cluster creado por la capa cluster/."
  type        = string
  default     = "kind-devops-platform"
}
