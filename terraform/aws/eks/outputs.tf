output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "configure_kubectl" {
  description = "Añade el cluster al kubeconfig; su contexto se usa como kube_context en envs/dev y envs/prod."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "github_actions_role_arn" {
  description = "Rol que asume el pipeline de CD (aws-actions/configure-aws-credentials)."
  value       = aws_iam_role.github_actions_deploy.arn
}
