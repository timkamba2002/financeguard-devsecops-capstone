output "vpc_id" {
  value       = aws_vpc.main.id
  description = "The ID of the VPC"
}

output "eks_cluster_name" {
  value       = aws_eks_cluster.main.name
  description = "The name of the EKS cluster"
}

output "eks_cluster_endpoint" {
  value       = aws_eks_cluster.main.endpoint
  description = "The endpoint URL of the EKS cluster"
}

output "rds_endpoint" {
  value       = aws_db_instance.main.endpoint
  description = "The connection endpoint of the RDS database"
}