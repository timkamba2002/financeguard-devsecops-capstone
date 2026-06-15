variable "aws_region" {
  type        = string
  description = "AWS region to deploy resources"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Target environment name (dev, staging, prod)"
  default     = "dev"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "List of availability zones for the subnets"
  default     = ["us-east-1a", "us-east-1b"]
}

variable "eks_cluster_name" {
  type        = string
  description = "Name of the EKS cluster"
  default     = "financeguard-eks"
}

variable "db_name" {
  type        = string
  description = "PostgreSQL database name"
  default     = "financeguard"
}

variable "db_user" {
  type        = string
  description = "Database administrator username"
  default     = "dbadmin"
}

variable "db_password" {
  type        = string
  description = "Database administrator password (use Secret Manager in production)"
  default     = "SuperSecretSecurePassword123!"
  sensitive   = true
}
