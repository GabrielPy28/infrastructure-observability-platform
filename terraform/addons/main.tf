# Capa 2 — add-ons compartidos por todo el cluster (no pertenecen a ningún entorno).

# metrics-server alimenta al HPA con el consumo de CPU/memoria de los pods.
resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  namespace  = "kube-system"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  version    = var.metrics_server_chart_version
  wait       = true
  timeout    = 300

  set = [
    {
      # Los kubelets de Kind usan certificados autofirmados.
      # Solo para entornos locales: en EKS/GKE no se necesita.
      name  = "args[0]"
      value = "--kubelet-insecure-tls"
    },
  ]
}
