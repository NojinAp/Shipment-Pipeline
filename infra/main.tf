terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "ca-central-1"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_s3_bucket" "shipment_pipeline" {
  bucket           = "enterprise-shipment-pipeline-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.region}-an"
  bucket_namespace = "account-regional"
}

resource "aws_iam_role" "glue_role" {
  name = "shipment-pipeline-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "glue_s3_access" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "glue_service_role" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role" "firehose_role" {
  name = "shipment-pipeline-firehose-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "firehose.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "firehose_s3_access" {
  role       = aws_iam_role.firehose_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "firehose_kinesis_access" {
  role       = aws_iam_role.firehose_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonKinesisFullAccess"
}

resource "aws_kinesis_stream" "scan_events" {
  name             = "shipment-pipeline-scan-events"
  shard_count      = 1
  retention_period = 24
}

resource "aws_kinesis_firehose_delivery_stream" "scan_events" {
  name        = "shipment-pipeline-scan-events-stream"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.scan_events.arn
    role_arn            = aws_iam_role.firehose_role.arn
  }

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose_role.arn
    bucket_arn = aws_s3_bucket.shipment_pipeline.arn
    prefix     = "extract/raw/scan_events/"

    buffering_size     = 1
    buffering_interval = 60
  }
}

resource "aws_s3_object" "shipment_master_staging" {
  bucket = aws_s3_bucket.shipment_pipeline.id
  key    = "redshift/staging/shipment_master.csv"
  source = "../sample_data/raw/shipment_master.csv"
  etag   = filemd5("../sample_data/raw/shipment_master.csv")
}

resource "aws_s3_object" "billing_extract_staging" {
  bucket = aws_s3_bucket.shipment_pipeline.id
  key    = "redshift/staging/billing_extract.csv"
  source = "../sample_data/raw/billing_extract.csv"
  etag   = filemd5("../sample_data/raw/billing_extract.csv")
}

resource "aws_s3_object" "extract_script" {
  bucket = aws_s3_bucket.shipment_pipeline.id
  key    = "scripts/extract.py"
  source = "../glue_jobs/extract.py"
  etag   = filemd5("../glue_jobs/extract.py")
}

resource "aws_s3_object" "transform_script" {
  bucket = aws_s3_bucket.shipment_pipeline.id
  key    = "scripts/transform.py"
  source = "../glue_jobs/transform.py"
  etag   = filemd5("../glue_jobs/transform.py")
}

resource "aws_s3_object" "load_script" {
  bucket = aws_s3_bucket.shipment_pipeline.id
  key    = "scripts/load.py"
  source = "../glue_jobs/load.py"
  etag   = filemd5("../glue_jobs/load.py") 
}

resource "aws_glue_job" "extract" {
  name     = "shipment-pipeline-extract"
  role_arn = aws_iam_role.glue_role.arn

  command {
    script_location = "s3://${aws_s3_bucket.shipment_pipeline.id}/${aws_s3_object.extract_script.key}"
    python_version   = "3"
  }

  default_arguments = {
    "--BUCKET_NAME" = aws_s3_bucket.shipment_pipeline.id
    "--job-language" = "python"
  }

  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"
}

resource "aws_glue_job" "transform" {
  name     = "shipment-pipeline-transform"
  role_arn = aws_iam_role.glue_role.arn

  command {
    script_location = "s3://${aws_s3_bucket.shipment_pipeline.id}/${aws_s3_object.transform_script.key}"
    python_version   = "3"
  }

  default_arguments = {
    "--BUCKET_NAME" = aws_s3_bucket.shipment_pipeline.id
    "--job-language" = "python"
  }

  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"
}

resource "aws_glue_job" "load" {
  name     = "shipment-pipeline-load"
  role_arn = aws_iam_role.glue_role.arn

  command {
    script_location = "s3://${aws_s3_bucket.shipment_pipeline.id}/${aws_s3_object.load_script.key}"
    python_version   = "3"
  }

  default_arguments = {
    "--BUCKET_NAME" = aws_s3_bucket.shipment_pipeline.id
    "--job-language" = "python"
  }

  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"
}