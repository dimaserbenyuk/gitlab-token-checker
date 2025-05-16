locals {
  aws_account_id = data.aws_caller_identity.current.account_id
  template_vars = {
    aws_account = local.aws_account_id
    region      = "us-east-1"
  }

  lambda_inline_policies = {
    for k, v in var.lambda_functions :
    k => length(v.inline_policy) > 0 ? v.inline_policy : (
      length(v.iam_policy_file) > 0 ? templatefile(v.iam_policy_file, local.template_vars) : null
    )
  }

  lambda_policy_arns = {
    for k, v in var.lambda_functions :
    k => length(v.policy_arn) > 0 ? v.policy_arn : null
  }

  lambda_executor_arn = startswith(var.role_of_lambda_executor, "arn:aws:iam::") ? var.role_of_lambda_executor : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.role_of_lambda_executor}"
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "iam_for_lambda" {
  for_each = var.lambda_functions

  name               = "iam_for_lambda_${each.key}"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

resource "aws_iam_policy" "inline" {
  for_each = local.lambda_inline_policies

  name        = "inline-${each.key}"
  description = "Inline policy for ${each.key}"
  policy      = each.value
}

resource "aws_iam_role_policy_attachment" "attach_inline_policy" {
  for_each = local.lambda_inline_policies

  role       = aws_iam_role.iam_for_lambda[each.key].name
  policy_arn = aws_iam_policy.inline[each.key].arn
}

resource "aws_iam_role_policy_attachment" "attach_lambda_policy" {
  for_each = { for k, v in var.lambda_functions : k => v if local.lambda_policy_arns[k] != null }

  role       = aws_iam_role.iam_for_lambda[each.key].name
  policy_arn = local.lambda_policy_arns[each.key]
}

resource "aws_iam_role_policy_attachment" "attach_secrets_manager_lambda_policy" {
  for_each = local.secrets_managers_to_create

  role       = aws_iam_role.iam_for_lambda[each.key].name
  policy_arn = aws_iam_policy.secrets_manager[each.key].arn
}

resource "aws_iam_role_policy_attachment" "attach_executor_policy" {
  for_each = var.lambda_functions

  role       = aws_iam_role.iam_for_lambda[each.key].name
  policy_arn = local.lambda_executor_arn
}
