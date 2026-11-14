import os
import json
import logging
from datetime import datetime, timezone
import boto3

from evaluator import (
    unmarshal_dynamodb_image,
    get_asset_metadata,
    evaluate_machine_health
)
from templates import build_incident_subject, format_incident_ticket

# Configure production logger for Amazon CloudWatch
logger = logging.getLogger("iot-stream-detector")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

sns_client = boto3.client('sns')
sqs_client = boto3.client('sqs')

SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')


def lambda_handler(event, context):
    """
    AWS Lambda entry point for DynamoDB Stream processing.
    Orchestrates record unmarshaling, health evaluation, SNS alerting, and SQS forwarding.

    Failure policy: per-record errors are logged and tracked individually.
    If any records fail, they are returned as batchItemFailures so DynamoDB
    Streams retries only the failed shards rather than blocking the whole batch.
    """
    records = event.get('Records', [])
    logger.info("Received DynamoDB Stream batch with %d records", len(records))

    records_processed = 0
    incidents_dispatched = 0
    sqs_forwarded = 0
    batch_item_failures = []

    for stream_record in records:
        sequence_number = stream_record.get('dynamodb', {}).get('SequenceNumber')
        event_name = stream_record.get('eventName')
        if event_name not in ('INSERT', 'MODIFY'):
            logger.debug("Skipping stream event type: %s", event_name)
            continue

        new_image = stream_record.get('dynamodb', {}).get('NewImage')
        if not new_image:
            continue

        try:
            # 1. Unmarshal and enrich record via evaluator module
            item = unmarshal_dynamodb_image(new_image)
            device_id = item.get('device_id', 'unknown')
            telemetry_id = item.get('telemetry_id', 'unknown')

            meta = get_asset_metadata(device_id)
            evaluation = evaluate_machine_health(item)

            item.update({
                "health_score": evaluation["health_score"],
                "severity": evaluation["severity"],
                "is_incident": evaluation["is_incident"],
                "anomaly_reasons": evaluation["anomaly_reasons"],
                "plant_location": meta["plant"],
                "maintenance_team": meta["team"],
                "evaluated_at": datetime.now(timezone.utc).isoformat()
            })

            # Log evaluation outcome at appropriate severity level
            if item["severity"] == "UNVALIDATED":
                logger.warning(
                    "Corrupted schema detected | telemetry_id=%s | device_id=%s | Deferring to SQS/DLQ",
                    telemetry_id, device_id
                )
            elif item["is_incident"]:
                logger.warning(
                    "Anomaly detected | telemetry_id=%s | device_id=%s | severity=%s | health_score=%d | reasons=%s",
                    telemetry_id, device_id, item["severity"], item["health_score"], item["anomaly_reasons"]
                )
            else:
                logger.info(
                    "Healthy telemetry evaluated | telemetry_id=%s | device_id=%s | health_score=%d",
                    telemetry_id, device_id, item["health_score"]
                )

            # 2. Dispatch real-time alert via SNS if record is an incident
            if item["is_incident"] and SNS_TOPIC_ARN:
                try:
                    sns_client.publish(
                        TopicArn=SNS_TOPIC_ARN,
                        Subject=build_incident_subject(item),
                        Message=format_incident_ticket(item)
                    )
                    incidents_dispatched += 1
                    logger.info("Published SNS incident ticket | telemetry_id=%s | device_id=%s", telemetry_id, device_id)
                except Exception as exc:
                    # SNS failure is non-fatal: log and continue so the record
                    # still flows to SQS for archival. The DLQ alarm will catch
                    # downstream failures independently.
                    logger.error("Failed to publish SNS alert | telemetry_id=%s | error=%s", telemetry_id, str(exc))

            # 3. Forward enriched payload to SQS for S3 Data Lake archival
            if SQS_QUEUE_URL:
                sqs_client.send_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MessageBody=json.dumps(item)
                )
                sqs_forwarded += 1

            records_processed += 1

        except Exception as exc:
            # Per-record failure: flag this sequence number so DynamoDB Streams
            # retries only this shard position rather than blocking the whole batch.
            logger.error(
                "Unrecoverable error processing stream record | sequenceNumber=%s | error=%s",
                sequence_number, str(exc)
            )
            if sequence_number:
                batch_item_failures.append({"itemIdentifier": sequence_number})

    logger.info(
        "Batch processing complete | processed=%d | incidents_alerted=%d | sqs_forwarded=%d | failures=%d",
        records_processed, incidents_dispatched, sqs_forwarded, len(batch_item_failures)
    )

    return {
        "statusCode": 200,
        "records_processed": records_processed,
        "incidents_dispatched": incidents_dispatched,
        "sqs_forwarded": sqs_forwarded,
        "batchItemFailures": batch_item_failures
    }