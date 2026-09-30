terraform {
  required_version = ">= 1.9"

  # State local, uno por entorno: un apply en dev nunca puede tocar prod.
  # En la nube: backend "s3" con cifrado y bloqueo (ver terraform/aws/).
  backend "local" {
    path = "terraform.tfstate"
  }

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.2"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.9"
    }
  }
}

provider "kubernetes" {
  config_path    = pathexpand(var.kubeconfig_path)
  config_context = var.kube_context
}
