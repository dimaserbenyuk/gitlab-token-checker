data "archive_file" "lambda_zip" {
  for_each         = { for k, v in var.lambda_functions : k => v if v.local_filename != "" }
  type             = "zip"
  output_file_mode = "0755"
  output_path      = format("%s.zip", pathexpand(each.value.local_filename))
  source_file      = each.value.local_filename
}

resource "aws_lambda_function" "lambda_function" {
  for_each         = var.lambda_functions
  function_name    = each.value.function_name
  role             = aws_iam_role.iam_for_lambda[each.key].arn
  handler          = each.value.handler
  runtime          = each.value.runtime
  memory_size      = each.value.memory_size
  timeout          = each.value.timeout
  filename         = each.value.function_s3_bucket == "" ? data.archive_file.lambda_zip[each.key].output_path : null
  source_code_hash = each.value.function_s3_bucket == "" ? data.archive_file.lambda_zip[each.key].output_base64sha256 : null
  s3_bucket        = each.value.local_filename == "" ? each.value.function_s3_bucket : null
  s3_key           = each.value.local_filename == "" ? each.value.function_s3_key : null

  dynamic "environment" {
    for_each = (
      [
        merge(
          each.value.environment_variables != null ? each.value.environment_variables : {},
          each.value.secrets_manager.enabled ? { AWS_SECRETS_MANAGER_ID = aws_secretsmanager_secret.this[each.key].id } : {}
        )
      ]
    )
    content {
      variables = environment.value
    }
  }

  dynamic "vpc_config" {
    for_each = (length(each.value.vpc_subnet_ids) > 0 && length(each.value.vpc_security_group_ids) > 0) ? [each.value] : []
    content {
      subnet_ids         = vpc_config.value.vpc_subnet_ids
      security_group_ids = vpc_config.value.vpc_security_group_ids
    }
  }

  depends_on = [aws_iam_role.iam_for_lambda]
}

resource "aws_cloudwatch_log_group" "lambda_log_group" {
  for_each = var.lambda_functions

  name              = "/aws/lambda/${each.value.function_name}"
  retention_in_days = each.value.log_retention_in_days
}

resource "aws_lambda_permission" "allow_s3_to_call_lambda" {
  for_each = { for k, v in var.lambda_functions : k => v if v.s3_trigger }

  statement_id  = "AllowS3InvokeLambda-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_function[each.key].function_name
  principal     = "s3.amazonaws.com"
  source_arn    = each.value.s3_trigger_bucket_arn
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  for_each = { for k, v in var.lambda_functions : k => v if v.s3_trigger }

  bucket = each.value.s3_trigger_bucket_name

  lambda_function {
    lambda_function_arn = aws_lambda_function.lambda_function[each.key].arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_s3_to_call_lambda]
}

# Trigger lambda function from event bus
resource "aws_cloudwatch_event_rule" "this" {
  for_each      = { for k, v in var.lambda_functions : k => v if v.event_bus }
  name          = each.key
  event_pattern = jsonencode(each.value.event_bus_pattern)
  depends_on    = [aws_lambda_function.lambda_function]
}

resource "aws_cloudwatch_event_target" "this" {
  for_each   = { for k, v in var.lambda_functions : k => v if v.event_bus }
  arn        = aws_lambda_function.lambda_function[each.key].arn
  rule       = aws_cloudwatch_event_rule.this[each.key].name
  depends_on = [aws_lambda_function.lambda_function]
}

resource "aws_lambda_permission" "event_bus" {
  for_each = { for k, v in var.lambda_functions : k => v if v.event_bus }

  function_name       = aws_lambda_function.lambda_function[each.key].function_name
  statement_id_prefix = each.key
  action              = "lambda:InvokeFunction"
  principal           = "events.amazonaws.com"
  source_arn          = aws_cloudwatch_event_rule.this[each.key].arn

  lifecycle {
    create_before_destroy = true
  }
}

# Trigger lambda by cron
resource "aws_cloudwatch_event_rule" "cron_schedule" {
  for_each = { for k, v in var.lambda_functions : k => v if v.cron_schedule_expression != null }

  name                = each.key
  schedule_expression = each.value.cron_schedule_expression
}

resource "aws_cloudwatch_event_target" "cron_schedule" {
  for_each = { for k, v in var.lambda_functions : k => v if v.cron_schedule_expression != null }

  arn  = aws_lambda_function.lambda_function[each.key].arn
  rule = aws_cloudwatch_event_rule.cron_schedule[each.key].name

  depends_on = [
    aws_lambda_function.lambda_function
  ]
}

resource "aws_lambda_permission" "cron_schedule" {
  for_each = { for k, v in var.lambda_functions : k => v if v.cron_schedule_expression != null }

  function_name       = aws_lambda_function.lambda_function[each.key].function_name
  statement_id_prefix = each.key
  action              = "lambda:InvokeFunction"
  principal           = "events.amazonaws.com"
  source_arn          = aws_cloudwatch_event_rule.cron_schedule[each.key].arn

  lifecycle {
    create_before_destroy = true
  }
}
