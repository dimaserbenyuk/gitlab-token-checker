terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.97.0"
    }
  }
}

provider "aws" {
  shared_config_files      = ["/Users/dima/.aws/config"]
  shared_credentials_files = ["/Users/dima/.aws/credentials"]
  profile                  = "default"
}
