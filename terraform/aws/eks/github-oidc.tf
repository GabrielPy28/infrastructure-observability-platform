# GitHub Actions se autentica en AWS con OIDC: el pipeline asume un rol de IAM
# con un token de corta duración, sin claves de acceso guardadas como secrets.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_actions_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Solo el pipeline de la rama main de este repositorio puede asumir el rol.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_actions_deploy" {
  name               = "${var.cluster_name}-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust.json
}

# Permiso mínimo en AWS: leer el endpoint del cluster para generar el
# kubeconfig. Lo que puede hacer dentro de Kubernetes lo limita la access
# entry de main.tf (AmazonEKSEditPolicy en los namespaces de la app).
data "aws_iam_policy_document" "describe_cluster" {
  statement {
    actions   = ["eks:DescribeCluster"]
    resources = [module.eks.cluster_arn]
  }
}

resource "aws_iam_role_policy" "describe_cluster" {
  name   = "describe-cluster"
  role   = aws_iam_role.github_actions_deploy.id
  policy = data.aws_iam_policy_document.describe_cluster.json
}
