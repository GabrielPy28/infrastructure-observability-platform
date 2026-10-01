# Equivalente en AWS de las capas locales cluster/ y addons/.
# Las capas envs/dev y envs/prod (módulo platform) y los manifiestos de
# Kustomize se reutilizan sin cambios: solo cambia el contexto de kubectl.

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 3)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.7"

  name = var.cluster_name
  cidr = var.vpc_cidr
  azs  = local.azs

  # Nodos en subredes privadas; las públicas solo alojan el NAT y los balanceadores.
  private_subnets = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, 48 + i)]

  enable_nat_gateway = true
  # Un solo NAT para reducir costes; en producción, uno por zona de disponibilidad.
  single_nat_gateway = true

  # El security group por defecto de la VPC queda sin reglas.
  manage_default_security_group = true

  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true

  # Etiquetas que usa Kubernetes para colocar balanceadores públicos e internos.
  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.26"

  name               = var.cluster_name
  kubernetes_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # API de Kubernetes accesible solo desde la VPC. Los runners de GitHub
  # cambian de IP, así que restringir un endpoint público por CIDR no es
  # viable: el CD se ejecuta en un runner self-hosted dentro de la VPC y los
  # administradores entran por VPN o SSM.
  endpoint_private_access = true
  endpoint_public_access  = false

  # Logs del control plane en CloudWatch (auditoría incluida).
  enabled_log_types = ["api", "audit", "authenticator"]

  # Quien ejecuta Terraform administra el cluster (equivale al kubeconfig de Kind).
  enable_cluster_creator_admin_permissions = true

  # Equivalente de la capa addons/: en EKS, metrics-server es un add-on
  # gestionado y no necesita --kubelet-insecure-tls.
  addons = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = { before_compute = true }
    eks-pod-identity-agent = { before_compute = true }
    metrics-server         = {}
  }

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      min_size       = var.node_scaling.min
      max_size       = var.node_scaling.max
      desired_size   = var.node_scaling.desired
    }
  }

  # El rol del pipeline de CD solo puede editar los namespaces de la aplicación.
  access_entries = {
    github_actions_deploy = {
      principal_arn = aws_iam_role.github_actions_deploy.arn
      policy_associations = {
        edit_app_namespaces = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"
          access_scope = {
            type       = "namespace"
            namespaces = var.app_namespaces
          }
        }
      }
    }
  }
}
