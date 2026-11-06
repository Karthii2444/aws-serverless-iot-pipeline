import os
import json
import logging
from datetime import datetime, timezone
import boto3

from validator import validate_telemetry_record, ValidationError
from s3_writer import write_batch_to_s3

logger = logging.getLogger("iot-batch-archiver")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

s3_client = boto3.client('s3')
S3_DATA_LAKE_BUCKET = os.environ.get('DATA_LAKE_BUCKET', '')


def lambda_handler(event, context):
    """
    Consumes SQS message batches, validates schemas, writes NDJSON to S3
    (telemetry/ and incidents/), and reports batch item failures for DLQ isolation.
    """
    records = event.get('Records', [])
    logger.info("Received SQS batch with %d messages", len(records))

    valid_telemetry_batch = []
    valid_incidents_batch = []
    batch_item_failures = []

    now = datetime.now(timezone.utc)

    for message in records:
        message_id = message.get('messageId')
        raw_body = message.get('body', '')

        try:
            payload = json.loads(raw_body)
            validated_record = validate_telemetry_record(payload)

            # Record is valid: append to general telemetry batch
            valid_telemetry_batch.append(validated_record)

            # If flagged as an incident, also route copy to incidents partition
            if validated_record.get('is_incident'):
                valid_incidents_batch.append(validated_record)

        except (json.JSONDecodeError, ValidationError) as exc:
            # Isolate individual poison pill message without failing the whole batch
            logger.warning(
                "Message validation failed | messageId=%s | error=%s | Flagging for DLQ retry",
                message_id, str(exc)
            )
            batch_item_failures.append({"itemIdentifier": message_id})
        except Exception as exc:
            logger.error("Unexpected error processing message | messageId=%s | error=%s", message_id, str(exc))
            batch_item_failures.append({"itemIdentifier": message_id})

    # Write validated telemetry to S3
    if valid_telemetry_batch and S3_DATA_LAKE_BUCKET:
        try:
            telemetry_key = write_batch_to_s3(
                s3_client, S3_DATA_LAKE_BUCKET, "telemetry", valid_telemetry_batch, now
            )
            logger.info("Archived telemetry batch to S3 | count=%d | s3_key=%s", len(valid_telemetry_batch), telemetry_key)
        except Exception as exc:
            logger.error("Failed writing telemetry to S3 | bucket=%s | error=%s", S3_DATA_LAKE_BUCKET, str(exc))
            raise

    # Write validated incidents to S3 incidents partition
    if valid_incidents_batch and S3_DATA_LAKE_BUCKET:
        try:
            incidents_key = write_batch_to_s3(
                s3_client, S3_DATA_LAKE_BUCKET, "incidents", valid_incidents_batch, now
            )
            logger.info("Archived incidents batch to S3 | count=%d | s3_key=%s", len(valid_incidents_batch), incidents_key)
        except Exception as exc:
            logger.error("Failed writing incidents to S3 | bucket=%s | error=%s", S3_DATA_LAKE_BUCKET, str(exc))
            raise

    logger.info(
        "Batch processing complete | total_received=%d | valid_telemetry=%d | valid_incidents=%d | failures=%d",
        len(records), len(valid_telemetry_batch), len(valid_incidents_batch), len(batch_item_failures)
    )

    # AWS Lambda SQS Partial Batch Response contract
    return {
        "batchItemFailures": batch_item_failures
    }