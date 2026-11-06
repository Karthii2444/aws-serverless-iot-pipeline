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

# Connect DynamoDB Stream to Detector Lambda
resource "aws_lambda_event_source_mapping" "dynamodb_stream_trigger" {
  event_source_arn  = aws_dynamodb_table.iot_telemetry.stream_arn
  function_name     = aws_lambda_function.detector.arn
  starting_position = "LATEST"
  batch_size        = 25
}