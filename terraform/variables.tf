variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "eks_cluster_name" {
  type    = string
  default = "financeguard-eks"
}

variable "db_name" {
  type    = string
  default = "financeguard"
}

variable "db_user" {
  type    = string
  default = "dbadmin"
}

variable "secret_name" {
  type    = string
  default = "financeguard/db/credentials"
}

variable "db_engine" {
  type        = string
  default     = "postgres"   # Change to "mysql" for your other project
  description = "Database engine: postgres or mysql"
}

variable "db_version" {
  type        = string
  default     = "16.14"       # For postgres. For mysql use "8.0"
}