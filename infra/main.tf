terraform {
  backend "s3" {
    bucket = "enterprise-shipment-pipeline-024532670007-ca-central-1-an"
    key    = "terraform/state/shipment-pipeline.tfstate"
    region = "ca-central-1"
    }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
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

variable "rds_password" {
  type      = string
  sensitive = true
}

variable "my_ip" {
  type    = string
  default = "136.226.130.83/32"
}

resource "aws_security_group" "rds_sg" {
  name   = "shipment-pipeline-rds-sg"
  vpc_id = "vpc-0a9f2dbb902bda42c"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "shipment-pipeline-rds-subnet-group"
  subnet_ids = ["subnet-073d19ab068f98059", "subnet-0d2ff734fcec39eba", "subnet-00caf19b0fe5f3299"]
}

resource "aws_db_instance" "shipment_source" {
  identifier             = "shipment-pipeline-source-db"
  engine                 = "postgres"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  db_name                = "shipment_source"
  username               = "postgres"
  password               = var.rds_password
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  publicly_accessible    = true
  skip_final_snapshot    = true
}

output "rds_endpoint" {
  value = aws_db_instance.shipment_source.address
}

resource "aws_iam_role" "rds_s3_import_role" {
  name = "shipment-pipeline-rds-s3-import-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_s3_read" {
  role       = aws_iam_role.rds_s3_import_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
}

resource "aws_db_instance_role_association" "rds_s3_import" {
  db_instance_identifier = aws_db_instance.shipment_source.identifier
  feature_name           = "s3Import"
  role_arn               = aws_iam_role.rds_s3_import_role.arn
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

resource "aws_s3_object" "transform_logic_script" {
  bucket = aws_s3_bucket.shipment_pipeline.id
  key    = "scripts/transform_logic.py"
  source = "../glue_jobs/transform_logic.py"
  etag   = filemd5("../glue_jobs/transform_logic.py")
}

resource "aws_s3_object" "load_logic_script" {
  bucket = aws_s3_bucket.shipment_pipeline.id
  key    = "scripts/load_logic.py"
  source = "../glue_jobs/load_logic.py"
  etag   = filemd5("../glue_jobs/load_logic.py")
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
    "--extra-py-files" = "s3://${aws_s3_bucket.shipment_pipeline.id}/${aws_s3_object.transform_logic_script.key}"
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
    "--extra-py-files" = "s3://${aws_s3_bucket.shipment_pipeline.id}/${aws_s3_object.load_logic_script.key}"
  }

  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"
}

resource "aws_iam_role" "step_functions_role" {
  name = "shipment-pipeline-step-functions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "step_functions_glue_access" {
  role       = aws_iam_role.step_functions_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess"
}

resource "aws_sfn_state_machine" "pipeline" {
  name     = "shipment-pipeline-orchestration"
  role_arn = aws_iam_role.step_functions_role.arn

  definition = jsonencode({
    Comment = "Extract -> Transform -> Load, sequential, stop on failure"
    StartAt = "Extract"
    States = {
      Extract = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.extract.name
        }
        Next = "Transform"
      }
      Transform = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.transform.name
        }
        Next = "Load"
      }
      Load = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = aws_glue_job.load.name
        }
        End = true
      }
    }
  })
}

resource "aws_iam_role" "lambda_produce_shipments_role" {
  name = "shipment-pipeline-lambda-produce-shipments-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_produce_shipments_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  role       = aws_iam_role.lambda_produce_shipments_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_security_group_rule" "rds_self_access" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds_sg.id
  source_security_group_id = aws_security_group.rds_sg.id
}

resource "aws_security_group_rule" "rds_my_ip_access" {
  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  security_group_id = aws_security_group.rds_sg.id
  cidr_blocks       = [var.my_ip]
}

data "archive_file" "lambda_produce_shipments" {
  type        = "zip"
  source_file = "../lambda_produce_shipments.py"
  output_path = "${path.module}/lambda_produce_shipments.zip"
}

resource "aws_lambda_function" "produce_shipments" {
  function_name = "shipment-pipeline-produce-shipments"
  role          = aws_iam_role.lambda_produce_shipments_role.arn
  handler       = "lambda_produce_shipments.lambda_handler"
  runtime       = "python3.12"
  filename         = data.archive_file.lambda_produce_shipments.output_path
  source_code_hash = data.archive_file.lambda_produce_shipments.output_base64sha256
  timeout       = 30

  vpc_config {
    subnet_ids         = ["subnet-073d19ab068f98059", "subnet-0d2ff734fcec39eba", "subnet-00caf19b0fe5f3299"]
    security_group_ids = [aws_security_group.rds_sg.id]
  }

  environment {
    variables = {
      RDS_HOST     = aws_db_instance.shipment_source.address
      RDS_PORT     = "5432"
      RDS_DB       = "shipment_source"
      RDS_USER     = "postgres"
      RDS_PASSWORD = var.rds_password
    }
  }
}

resource "aws_cloudwatch_event_rule" "produce_shipments_schedule" {
  name                = "shipment-pipeline-produce-shipments-schedule"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "produce_shipments_target" {
  rule = aws_cloudwatch_event_rule.produce_shipments_schedule.name
  arn  = aws_lambda_function.produce_shipments.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.produce_shipments.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.produce_shipments_schedule.arn
}

resource "aws_sns_topic" "pipeline_alerts" {
  name = "shipment-pipeline-alerts"
}

resource "aws_sns_topic_subscription" "pipeline_alerts_email" {
  topic_arn = aws_sns_topic.pipeline_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email 
}

resource "aws_cloudwatch_event_rule" "glue_job_failures" {
  name        = "shipment-pipeline-glue-failures"
  description = "Triggers on FAILED/TIMEOUT/STOPPED state for the pipeline's Glue jobs"

  event_pattern = jsonencode({
    source      = ["aws.glue"]
    detail-type = ["Glue Job State Change"]
    detail = {
      jobName = [
        "extract",  
        "transform",
        "load"
      ]
      state = ["FAILED", "TIMEOUT", "STOPPED"]
    }
  })
}

resource "aws_cloudwatch_event_target" "glue_failures_to_sns" {
  rule      = aws_cloudwatch_event_rule.glue_job_failures.name
  target_id = "sns-alert"
  arn       = aws_sns_topic.pipeline_alerts.arn
}

resource "aws_sns_topic_policy" "allow_eventbridge" {
  arn = aws_sns_topic.pipeline_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowEventBridgePublish"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sns:Publish"
      Resource  = aws_sns_topic.pipeline_alerts.arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.glue_job_failures.arn }
      }
    }]
  })
}

resource "aws_cloudwatch_metric_alarm" "stepfunction_failures" {
  alarm_name          = "shipment-pipeline-stepfunction-failures"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods   = 1
  metric_name          = "ExecutionsFailed"
  namespace             = "AWS/States"
  period                = 300
  statistic             = "Sum"
  threshold             = 1
  treat_missing_data   = "notBreaching"
  alarm_description    = "Fires when the shipment pipeline state machine has a failed execution"

  dimensions = {
    StateMachineArn = aws_sfn_state_machine.pipeline.arn
  }

  alarm_actions = [aws_sns_topic.pipeline_alerts.arn]
}

resource "aws_glue_catalog_database" "shipment_pipeline_db" {
  name = "shipment_pipeline_db"
}

resource "aws_glue_crawler" "load_crawler" {
  name          = "shipment-pipeline-load-crawler"
  role          = aws_iam_role.glue_role.arn
  database_name = aws_glue_catalog_database.shipment_pipeline_db.name

  s3_target {
    path = "s3://${aws_s3_bucket.shipment_pipeline.id}/load/"
  }
}