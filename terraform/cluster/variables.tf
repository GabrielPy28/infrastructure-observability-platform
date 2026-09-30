variable "cluster_name" {
  description = "Nombre del cluster Kind. El contexto de kubectl será kind-<cluster_name>."
  type        = string
  default     = "devops-platform"
}

variable "node_image" {
  description = "Imagen de nodo de Kind; fija la versión de Kubernetes."
  type        = string
  # Debe corresponder a la versión de kind que incluye el provider
  # (tehcyx/kind 0.11 -> kind v0.31.0). Una imagen más nueva falla en
  # "kubeadm init". Fijada por digest para que sea reproducible.
  default = "kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f"
}

variable "worker_count" {
  description = "Número de nodos worker además del control-plane."
  type        = number
  default     = 2

  validation {
    condition     = var.worker_count >= 1 && var.worker_count <= 3
    error_message = "worker_count debe estar entre 1 y 3 (cluster local)."
  }
}

variable "kubeconfig_path" {
  description = "Kubeconfig donde se fusiona el contexto del cluster."
  type        = string
  default     = "~/.kube/config"
}
