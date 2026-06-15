# RDS Database Subnet Group
resource "aws_db_subnet_group" "main" {
  name        = "financeguard-db-subnet-group-${var.environment}"
  description = "Database subnet group for FinanceGuard PostgreSQL"
  subnet_ids  = aws_subnet.database[*].id

  tags = {
    Name = "financeguard-db-subnet-group-${var.environment}"
  }
}

# RDS Security Group
resource "aws_security_group" "db" {
  name        = "financeguard-db-sg-${var.environment}"
  description = "Access to RDS from EKS worker nodes only"
  vpc_id      = aws_vpc.main.id

  # Ingress rule allowing traffic from EKS node security group or private subnet blocks
  ingress {
    description = "Allow PostgreSQL access from EKS private subnets"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = aws_subnet.private[*].cidr_block
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "financeguard-db-sg-${var.environment}"
  }
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "main" {
  identifier             = "financeguard-db-${var.environment}"
  allocated_storage      = 20
  max_allocated_storage  = 100
  db_name                = var.db_name
  engine                 = "postgres"
  engine_version         = "15.7"
  instance_class         = "db.t3.micro"
  username               = var.db_user
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  skip_final_snapshot    = true
  multi_az               = var.environment == "prod" ? true : false
  storage_encrypted      = true

  tags = {
    Name = "financeguard-rds-postgres-${var.environment}"
  }
}
