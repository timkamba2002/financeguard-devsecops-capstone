# RDS Database Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "financeguard-db-subnet-group-${var.environment}"
  subnet_ids = aws_subnet.database[*].id
}

# RDS Security Group - Allow access from EKS Fargate
resource "aws_security_group" "db" {
  name        = "financeguard-db-sg-${var.environment}"
  description = "Allow EKS Fargate to connect to RDS"
  vpc_id      = aws_vpc.main.id

  ingress {
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

# Secret in AWS Secrets Manager
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = var.secret_name
  description = "FinanceGuard RDS Database Credentials"
}

resource "aws_secretsmanager_secret_version" "db_credentials_version" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_user
    password = "ChangeMeToAStrongPassword123!"   # Change this in console later
  })
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "main" {
  identifier             = "financeguard-db-${var.environment}"
  allocated_storage      = 20
  engine                 = var.db_engine
  engine_version         = var.db_version
  instance_class         = var.db_engine == "mysql" ? "db.t3.micro" : "db.t3.micro"
  db_name                = var.db_name
  username               = var.db_user
  password               = jsondecode(aws_secretsmanager_secret_version.db_credentials_version.secret_string)["password"]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  skip_final_snapshot    = true
  storage_encrypted      = true

  tags = {
    Name = "financeguard-rds-${var.environment}"
  }
}