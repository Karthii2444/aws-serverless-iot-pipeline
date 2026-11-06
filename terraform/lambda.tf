# Package the simulator Python source code into a zip archive
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
    }
  }
}

# Public Lambda Function URL for Postman invocations
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