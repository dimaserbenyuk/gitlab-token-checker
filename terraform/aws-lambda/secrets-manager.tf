locals {
  secrets_managers_to_create = { for k, v in var.lambda_functions : k => v.secrets_manager if v.secrets_manager.enabled }
}

resource "aws_kms_key" "this" {
  for_each = local.secrets_managers_to_create

  description             = format("Key for lambda %s", each.key)
  enable_key_rotation     = true
  deletion_window_in_days = each.value.recovery_window_in_days

  policy = jsonencode(
    {
      Version = "2012-10-17",
      Id      = format("key-policy-%s", each.key),
      Statement = [
        {
          Sid    = "Enable IAM User Permissions",
          Effect = "Allow",
          Principal = {
            AWS = format("arn:aws:iam::%s:root", local.aws_account_id)
          },
          Action   = "kms:*",
          Resource = "*"
        },
        {
          Sid    = "AllowTerrformProviderAccess",
          Effect = "Allow",
          Principal = {
            AWS = var.role_of_lambda_provider
          },
          Action = [
            "kms:Encrypt",
            "kms:Decrypt",
            "kms:GenerateDataKey"
          ]
          Resource = "*"
        }
      ]
    }
  )
}

resource "aws_kms_alias" "this" {
  for_each = local.secrets_managers_to_create

  name          = format("alias/lambda/%s", each.key)
  target_key_id = aws_kms_key.this[each.key].arn
}

resource "aws_secretsmanager_secret" "this" {
  for_each = local.secrets_managers_to_create

  description             = format("Secret for lambda %s", each.key)
  name                    = format("lambda/%s", each.key)
  kms_key_id              = aws_kms_key.this[each.key].arn
  recovery_window_in_days = each.value.recovery_window_in_days
}

data "aws_iam_policy_document" "secrets_manager" {
  for_each = local.secrets_managers_to_create

  statement {
    effect    = "Allow"
    actions   = ["secretsmanager:ListSecrets"]
    resources = ["*"]
  }

  statement {
    effect    = "Allow"
    resources = [aws_secretsmanager_secret.this[each.key].arn]

    actions = [
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:ListSecretVersionIds"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey"
    ]
    resources = [aws_kms_key.this[each.key].arn]
  }
}

resource "aws_iam_policy" "secrets_manager" {
  for_each = local.secrets_managers_to_create

  name        = format("lambda-%s", each.key)
  description = format("A policy for lambda function %s", each.key)
  policy      = data.aws_iam_policy_document.secrets_manager[each.key].json
}
