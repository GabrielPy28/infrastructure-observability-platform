output "metrics_server_version" {
  value = helm_release.metrics_server.metadata.app_version
}
