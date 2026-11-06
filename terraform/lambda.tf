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

  # Enables partial batch failure reporting (ReportBatchItemFailures contract)
  function_response_types = ["ReportBatchItemFailures"]
}