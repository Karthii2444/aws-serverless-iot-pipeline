import json
import uuid
from datetime import datetime, timezone

S3_INGESTION_SOURCE = "iot-batch-archiver"


def build_hive_s3_key(prefix, dt=None):
    """
    Constructs an hourly Hive partition path:
    <prefix>/year=YYYY/month=MM/day=DD/hour=HH/batch_<uuid>.jsonl
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    file_id = str(uuid.uuid4())[:8]
    return (
        f"{prefix}/year={dt.year}/month={dt.month:02d}/day={dt.day:02d}/"
        f"hour={dt.hour:02d}/batch_{file_id}.jsonl"
    )


def serialize_to_ndjson(records):
    """
    Serializes a list of dictionaries into Athena-optimized Newline-Delimited JSON.
    Each record is placed on its own line without comma delimiters.
    """
    return "\n".join(json.dumps(record, separators=(',', ':')) for record in records) + "\n"


def write_batch_to_s3(s3_client, bucket_name, prefix, records, dt=None):
    """
    Uploads an NDJSON batch to S3 with audit metadata headers.
    Returns the generated S3 object key.
    """
    if not records:
        return None

    if dt is None:
        dt = datetime.now(timezone.utc)

    s3_key = build_hive_s3_key(prefix, dt)
    ndjson_body = serialize_to_ndjson(records)
    incident_count = sum(1 for r in records if r.get('is_incident'))

    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=ndjson_body.encode('utf-8'),
        ContentType='application/x-ndjson',
        Metadata={
            'record-count': str(len(records)),
            'incident-count': str(incident_count),
            'ingestion-source': S3_INGESTION_SOURCE,
            'archived-at': dt.isoformat()
        }
    )

    return s3_key