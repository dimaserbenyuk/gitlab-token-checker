data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1"
  ]

  tags = {
    Name = "GitHub-Actions-OIDC-Provider"
  }
}

locals {
  github_subjects = [
    for repo in var.github_repositories :
    "repo:${repo.org}/${repo.repo}:${lookup(repo, "branch", "*")}"
  ]
}

resource "aws_iam_role" "github_oidc" {
  name = "GitHubOIDCRoleForLambdaDeploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        },
        Action = "sts:AssumeRoleWithWebIdentity",
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          },
          StringLike = {
            "token.actions.githubusercontent.com:sub" = local.github_subjects
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "s3_upload_lambda" {
  name = "AllowS3LambdaZipUpload"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ],
        Resource = "arn:aws:s3:::your-bucket-name/lambdas/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_s3_policy" {
  role       = aws_iam_role.github_oidc.name
  policy_arn = aws_iam_policy.s3_upload_lambda.arn
}
