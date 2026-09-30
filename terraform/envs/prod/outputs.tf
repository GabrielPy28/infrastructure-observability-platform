output "namespace" {
  value = module.platform.namespace
}

output "secret_name" {
  value = module.platform.secret_name
}

output "api_key" {
  description = "Consultar con: terraform output -raw api_key"
  value       = module.platform.api_key
  sensitive   = true
}
