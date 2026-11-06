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

# Connect SQS Main Queue to Archiver Lambda with Partial Batch Response
resource "aws_lambda_event_source_mapping" "sqs_to_archiver" {
  event_source_arn = aws_sqs_queue.telemetry_queue.arn
  function_name    = aws_lambda_function.archiver.arn
  batch_size       = 10

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

# Connect DynamoDB Stream to Detector Lambda
resource "aws_lambda_event_source_mapping" "dynamodb_stream_trigger" {
  event_source_arn  = aws_dynamodb_table.iot_telemetry.stream_arn
  function_name     = aws_lambda_function.detector.arn
  starting_position = "LATEST"
  batch_size        = 25
  # Enables partial batch failure reporting (ReportBatchItemFailures contract)
  function_response_types = ["ReportBatchItemFailures"]
}