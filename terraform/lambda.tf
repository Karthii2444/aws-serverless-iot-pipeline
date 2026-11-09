# ====================================================================
# 1. Simulator Lambda (Lambda 0)
# ====================================================================
data "archive_file" "simulator_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../simulator-lambda/src"
  output_path = "${path.module}/simulator.zip"
}

resource "aws_lambda_function" "simulator" {
  function_name    = "iot-simulator"
  role             = aws_iam_role.simulator_role.arn
  handler          = "main.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.simulator_zip.output_path
  source_code_hash = data.archive_file.simulator_zip.output_base64sha256

  timeout     = 15
  memory_size = 128

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.iot_telemetry.name
      LOG_LEVEL  = "INFO"
    }
  }
}

resource "aws_lambda_function_url" "simulator_url" {
  function_name      = aws_lambda_function.simulator.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST"]
    allow_headers     = ["content-type"]
    max_age           = 86400
  }
}

# ====================================================================
# 2. Stream Detector Lambda (Lambda 1)
# ====================================================================
data "archive_file" "detector_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../detector-lambda/src"
  output_path = "${path.module}/detector.zip"
}

resource "aws_lambda_function" "detector" {
  function_name    = "iot-stream-detector"
  role             = aws_iam_role.detector_role.arn
  handler          = "main.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.detector_zip.output_path
  source_code_hash = data.archive_file.detector_zip.output_base64sha256

  timeout     = 15
  memory_size = 128

  environment {
    variables = {
      SNS_TOPIC_ARN       = aws_sns_topic.iot_alerts.arn
      SQS_QUEUE_URL       = aws_sqs_queue.telemetry_queue.id
      PLANT_METADATA_JSON = jsonencode(var.plant_metadata)
      LOG_LEVEL           = "INFO"
    }
  }
}

resource "aws_lambda_event_source_mapping" "dynamodb_stream_trigger" {
  event_source_arn  = aws_dynamodb_table.iot_telemetry.stream_arn
  function_name     = aws_lambda_function.detector.arn
  starting_position = "LATEST"
  batch_size        = 25
}

# ====================================================================
# 3. Batch Archiver Lambda (Lambda 2)
# ====================================================================
data "archive_file" "archiver_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../archiver-lambda/src"
  output_path = "${path.module}/archiver.zip"
}

resource "aws_lambda_function" "archiver" {
  function_name    = "iot-batch-archiver"
  role             = aws_iam_role.archiver_role.arn
  handler          = "main.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.archiver_zip.output_path
  source_code_hash = data.archive_file.archiver_zip.output_base64sha256

  timeout     = 30
  memory_size = 256

  environment {
    variables = {
      DATA_LAKE_BUCKET = aws_s3_bucket.data_lake.id
      LOG_LEVEL        = "INFO"
    }
  }
}

resource "aws_lambda_event_source_mapping" "sqs_to_archiver" {
  event_source_arn        = aws_sqs_queue.telemetry_queue.arn
  function_name           = aws_lambda_function.archiver.arn
  batch_size              = 10
  function_response_types = ["ReportBatchItemFailures"]
}

# ====================================================================
# 4. Daily Executive Reporter Lambda (Lambda 3)
# ====================================================================
data "archive_file" "reporter_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../reporter-lambda/src"
  output_path = "${path.module}/reporter.zip"
}

resource "aws_lambda_function" "reporter" {
  function_name    = "iot-daily-reporter"
  role             = aws_iam_role.reporter_role.arn
  handler          = "main.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.reporter_zip.output_path
  source_code_hash = data.archive_file.reporter_zip.output_base64sha256

  timeout     = 60
  memory_size = 256

  environment {
    variables = {
      ATHENA_DATABASE  = aws_athena_database.iot_db.name
      ATHENA_WORKGROUP = aws_athena_workgroup.iot_workgroup.name
      DATA_LAKE_BUCKET = aws_s3_bucket.data_lake.id
      SENDER_EMAIL     = var.alert_email
      RECEIVER_EMAIL   = var.alert_email
      LOG_LEVEL        = "INFO"
    }
  }
}

resource "aws_cloudwatch_event_rule" "daily_report_schedule" {
  name                = "iot-daily-report-cron"
  description         = "Triggers Lambda 3 daily to compile Athena executive report"
  schedule_expression = "cron(0 0 * * ? *)"
}

resource "aws_cloudwatch_event_target" "trigger_reporter_lambda" {
  rule      = aws_cloudwatch_event_rule.daily_report_schedule.name
  target_id = "TriggerDailyReporter"
  arn       = aws_lambda_function.reporter.arn
}

resource "aws_lambda_permission" "allow_eventbridge_to_reporter" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reporter.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_report_schedule.arn
}