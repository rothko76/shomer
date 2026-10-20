variable "cluster_name" {
  type    = string
  default = "shomer"
}

variable "kubernetes_version" {
  type    = string
  default = "v1.30.0"
}

variable "workers" {
  type    = number
  default = 1
}

variable "ingress_http_port" {
  type    = number
  default = 8080
}

variable "ingress_https_port" {
  type    = number
  default = 8443
}
