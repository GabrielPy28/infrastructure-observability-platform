terraform {
  required_version = ">= 1.10"

  # State remoto en S3 con cifrado y bloqueo nativo (use_lockfile, sin DynamoDB).
  # Configuración parcial: los valores se pasan en el init (ver backend.hcl.example).
  #   terraform init -backend-config=backend.hcl
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.67"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "infrastructure-observability-platform"
      ManagedBy = "terraform"
    }
  }
}
