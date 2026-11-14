# S3 Bucket for storing Athena query execution results
resource "aws_s3_bucket" "athena_results" {
  bucket        = "iot-athena-query-results-${random_string.bucket_suffix.result}"
  force_destroy = true # Automatically empties bucket on destroy

  tags = {
    Name = "iot-athena-query-results"
  }
}

# Auto-delete query results older than 2 days to stay safely in Free Tier
resource "aws_s3_bucket_lifecycle_configuration" "athena_results_lifecycle" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "clean-old-query-results"
    status = "Enabled"

    filter {}

    expiration {
      days = 2
    }
  }
}

# Athena Database (with force_destroy enabled for external tables)
resource "aws_athena_database" "iot_db" {
  name          = "iot_telemetry_db"
  bucket        = aws_s3_bucket.athena_results.id
  force_destroy = true # Drops registered tables automatically on destroy
}

# Athena Workgroup (with force_destroy enabled for query history)
resource "aws_athena_workgroup" "iot_workgroup" {
  name          = "iot-analytics-workgroup"
  force_destroy = true # Deletes workgroup even if query history exists

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.id}/output/"
    }
  }
}

# ====================================================================
# Glue Catalog Tables (used by Amazon Athena for SQL queries)
# Athena's metastore IS the AWS Glue Data Catalog — defining tables
# here is equivalent to running CREATE EXTERNAL TABLE in the query editor.
# ====================================================================

locals {
  # Shared column schema for both telemetry and incidents tables
  telemetry_columns = [
    { name = "device_id", type = "string" },
    { name = "timestamp", type = "string" },
    { name = "telemetry_id", type = "string" },
    { name = "device_type", type = "string" },
    { name = "temperature_c", type = "double" },
    { name = "vibration_hz", type = "double" },
    { name = "pressure_psi", type = "double" },
    { name = "battery_pct", type = "int" },
    { name = "status", type = "string" },
    { name = "health_score", type = "int" },
    { name = "severity", type = "string" },
    { name = "is_incident", type = "boolean" },
    { name = "anomaly_reasons", type = "array<string>" },
    { name = "plant_location", type = "string" },
    { name = "maintenance_team", type = "string" },
    { name = "evaluated_at", type = "string" },
  ]

  # Hive partition columns written by the Archiver Lambda (year=/month=/day=/hour=)
  hive_partition_columns = [
    { name = "year", type = "string" },
    { name = "month", type = "string" },
    { name = "day", type = "string" },
    { name = "hour", type = "string" },
  ]
}

# Glue table: iot_telemetry_db.telemetry
# Points to s3://<data-lake>/telemetry/ — all enriched sensor readings
resource "aws_glue_catalog_table" "telemetry" {
  database_name = aws_athena_database.iot_db.name
  name          = "telemetry"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "classification"        = "json"
    "has_encrypted_data"    = "false"
    "ignore.malformed.json" = "true"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data_lake.id}/telemetry/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
      parameters = {
        "ignore.malformed.json" = "true"
      }
    }

    dynamic "columns" {
      for_each = local.telemetry_columns
      content {
        name = columns.value.name
        type = columns.value.type
      }
    }
  }

  dynamic "partition_keys" {
    for_each = local.hive_partition_columns
    content {
      name = partition_keys.value.name
      type = partition_keys.value.type
    }
  }
}

# Glue table: iot_telemetry_db.incidents
# Points to s3://<data-lake>/incidents/ — only WARNING and CRITICAL records
resource "aws_glue_catalog_table" "incidents" {
  database_name = aws_athena_database.iot_db.name
  name          = "incidents"

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "classification"        = "json"
    "has_encrypted_data"    = "false"
    "ignore.malformed.json" = "true"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data_lake.id}/incidents/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
      parameters = {
        "ignore.malformed.json" = "true"
      }
    }

    dynamic "columns" {
      for_each = local.telemetry_columns
      content {
        name = columns.value.name
        type = columns.value.type
      }
    }
  }

  dynamic "partition_keys" {
    for_each = local.hive_partition_columns
    content {
      name = partition_keys.value.name
      type = partition_keys.value.type
    }
  }
}