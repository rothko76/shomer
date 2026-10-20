output "name" {
  value = kind_cluster.this.name
}

output "context" {
  value       = "kind-${kind_cluster.this.name}"
  description = "kubeconfig context name."
}

output "endpoint" {
  value = kind_cluster.this.endpoint
}

output "kubeconfig_path" {
  value = kind_cluster.this.kubeconfig_path
}
