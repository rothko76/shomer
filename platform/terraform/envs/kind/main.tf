# Local, always-on environment. State is local (gitignored); a remote backend arrives with EKS.
terraform {
  required_version = ">= 1.6"

  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "~> 0.6"
    }
  }
}

provider "kind" {}

module "cluster" {
  source = "../../modules/kind-cluster"

  name               = var.cluster_name
  kubernetes_version = var.kubernetes_version
  workers            = var.workers
  # 8080/8443 by default, so this coexists with other kind clusters that hold 80/443.
  ingress_http_port  = var.ingress_http_port
  ingress_https_port = var.ingress_https_port
}
