output "context" {
  value = module.cluster.context
}

output "endpoint" {
  value = module.cluster.endpoint
}

output "ingress_url" {
  value = "http://localhost:${var.ingress_http_port}"
}
