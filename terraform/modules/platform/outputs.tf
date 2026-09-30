output "namespace" {
  value = kubernetes_namespace_v1.this.metadata[0].name
}

output "secret_name" {
  value = kubernetes_secret_v1.api.metadata[0].name
}

output "api_key" {
  value     = random_password.api_key.result
  sensitive = true
}
