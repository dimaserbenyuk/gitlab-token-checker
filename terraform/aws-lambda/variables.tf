variable "role_of_lambda_executor" {
  description = "Lifecycle Management lambda_executor"
  type        = string
  default     = ""
}

variable "role_of_lambda_provider" {
  description = "IAM Role ARN of the Lambda provider that needs access to the KMS key"
  type        = string
}


variable "lambda_functions" {
  description = "A map of Lambda function configurations"
  type = map(
    object(
      {
        cron_schedule_expression = optional(string, null)
        environment_variables    = optional(map(string), {})
        event_bus                = optional(bool, false)
        event_bus_pattern        = optional(any, null)
        existing_policy_list     = optional(list(string), [])
        function_name            = string
        function_s3_bucket       = optional(string, "")
        function_s3_key          = optional(string, "")
        handler                  = string
        iam_policy_file          = optional(string, "")
        inline_policy            = optional(string, "")
        local_filename           = optional(string, "")
        log_retention_in_days    = optional(number, 14)
        memory_size              = optional(number, 128)
        policy_arn               = optional(string, "")
        runtime                  = string
        s3_trigger               = optional(bool, false)
        s3_trigger_bucket_arn    = optional(string, "")
        s3_trigger_bucket_name   = optional(string, "")
        timeout                  = optional(number, 3)
        vpc_security_group_ids   = optional(list(string), [])
        vpc_subnet_ids           = optional(list(string), [])
        secrets_manager = optional(
          object(
            {
              enabled                 = optional(bool, false)
              recovery_window_in_days = optional(number, 7)
            }
          ),
          {}
        )
      }
    )
  )
}
