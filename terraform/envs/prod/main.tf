module "platform" {
  source = "../../modules/platform"

  environment = "prod"

  # prod: HPA 2-4 réplicas + 1 de surge = 5 pods (límites 2500m / 1280Mi).
  quota = {
    requests_cpu    = "1"
    requests_memory = "1Gi"
    limits_cpu      = "3"
    limits_memory   = "2Gi"
    pods            = 10
  }
}
