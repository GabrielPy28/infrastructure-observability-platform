output "cluster_name" {
  value = kind_cluster.this.name
}

output "kube_context" {
  description = "Contexto de kubectl que usan las capas addons/ y envs/."
  value       = "kind-${kind_cluster.this.name}"
}

output "endpoint" {
  value = kind_cluster.this.endpoint
}
