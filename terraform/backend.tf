resource "aws_s3_bucket" "tfstate" {
  bucket = "financeguard-tfstate"

  tags = {
    Name = "FinanceGuard Terraform State"
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_dynamodb_table" "tfstate_lock" {
  name         = "financeguard-tfstate-lock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name = "FinanceGuard Terraform Lock"
  }
}