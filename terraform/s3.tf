# Random string suffix to ensure globally unique S3 bucket naming
resource "random_string" "bucket_suffix" {
  length  = 6
  special = false
  upper   = false
}

# Main S3 Data Lake Bucket for telemetry/ and incidents/
resource "aws_s3_bucket" "data_lake" {
  bucket = "iot-telemetry-lake-${random_string.bucket_suffix.result}"
  force_destroy = true

  tags = {
    Name = "iot-telemetry-lake"
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "data_lake_public_block" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable default server-side encryption (SSE-S3)
resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake_encryption" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle rule: automatically transition or cleanup old data
resource "aws_s3_bucket_lifecycle_configuration" "data_lake_lifecycle" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    id     = "archive-old-telemetry"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = 90
    }
  }
}