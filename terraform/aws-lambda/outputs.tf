output "secrets_manager_arns" {
  description = "A map of secrets manager ARNs per lambda function"
  value       = { for k, v in local.secrets_managers_to_create : k => aws_secretsmanager_secret.this[k].arn }
}

output "kms_key_ids" {
  description = "A map of KMS key IDs per lambda function"
  value       = { for k, v in local.secrets_managers_to_create : k => aws_kms_key.this[k].key_id }
}

output "kms_key_arns" {
  description = "A map of KMS key ARNs per lambda function"
  value       = { for k, v in local.secrets_managers_to_create : k => aws_kms_key.this[k].arn }
}
