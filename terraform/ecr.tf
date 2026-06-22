resource "aws_ecr_repository" "backend" {
  name = "financeguard-backend"
}

resource "aws_ecr_repository" "frontend" {
  name = "financeguard-frontend"
}

resource "aws_iam_policy" "ecr_pull" {
  name = "financeguard-ecr-pull"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "node_ecr_pull" {
  policy_arn = aws_iam_policy.ecr_pull.arn
  role       = aws_iam_role.eks_nodes.name
}