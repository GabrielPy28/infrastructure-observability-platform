terraform {
  required_version = ">= 1.9"

  backend "local" {
    path = "terraform.tfstate"
  }

  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "~> 0.11"
    }
  }
}
