module "platform" {
  source = "../../modules/platform"

  environment = "dev"

  # dev: HPA 1-2 réplicas + 1 de surge = 3 pods (límites 1500m / 768Mi).
  quota = {
    requests_cpu    = "500m"
    requests_memory = "512Mi"
    limits_cpu      = "2"
    limits_memory   = "1Gi"
    pods            = 6
  }
}
