resource "kind_cluster" "this" {
  name           = var.name
  node_image     = "kindest/node:${var.kubernetes_version}"
  wait_for_ready = true

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    # The ingress controller is pinned to this node via the ingress-ready label.
    node {
      role = "control-plane"

      kubeadm_config_patches = [
        <<-EOT
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
        EOT
      ]

      extra_port_mappings {
        container_port = 80
        host_port      = var.ingress_http_port
        listen_address = var.listen_address
        protocol       = "TCP"
      }

      extra_port_mappings {
        container_port = 443
        host_port      = var.ingress_https_port
        listen_address = var.listen_address
        protocol       = "TCP"
      }
    }

    dynamic "node" {
      for_each = range(var.workers)
      content {
        role = "worker"
      }
    }
  }
}
