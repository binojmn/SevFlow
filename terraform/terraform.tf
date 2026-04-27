terraform {

  backend "s3" {
    bucket = "sevflow-terraform-backend-bucket"
    key    = "s3-backend"
    region = "us-east-1"
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.37.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
