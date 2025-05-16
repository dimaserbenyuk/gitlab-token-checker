module "test_lambda" {
  source = "./aws-lambda"

  role_of_lambda_executor = "arn:aws:iam::272509770066:policy/inline-hello_world" #"arn:aws:iam::272509770066:policy/LambdaExecutionRole"
  role_of_lambda_provider = "LambdaSecretsManagerProvider"

  lambda_functions = {
    hello_world = {
      function_name         = "hello-world"
      handler               = "lambda_function.lambda_handler"
      runtime               = "python3.11"
      iam_policy_file       = "${path.module}/policies/basic_logs.json"
      local_filename        = "${path.module}/lambda/lambda_function.py"
      memory_size           = 128
      timeout               = 3
      log_retention_in_days = 7
      secrets_manager = {
        enabled                 = false
        recovery_window_in_days = 7
      }
    }
  }
}
