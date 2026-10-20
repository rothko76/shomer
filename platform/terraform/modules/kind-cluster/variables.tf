variable "name" {
  type        = string
  description = "Cluster name. The kubeconfig context is kind-<name>."
}

variable "kubernetes_version" {
  type        = string
  default     = "v1.30.0"
  description = "kindest/node image tag."
}

variable "workers" {
  type        = number
  default     = 1
  description = "Number of worker nodes."

  validation {
    condition     = var.workers >= 0 && var.workers <= 5
    error_message = "workers must be between 0 and 5."
  }
}

variable "ingress_http_port" {
  type        = number
  default     = 8080
  description = "Host port mapped to the ingress controller's port 80."
}

variable "ingress_https_port" {
  type        = number
  default     = 8443
  description = "Host port mapped to the ingress controller's port 443."
}

variable "listen_address" {
  type        = string
  default     = "127.0.0.1"
  description = "Host address the ingress ports bind to. Keep it on loopback."
}
