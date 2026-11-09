import os
import json
import random
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
import boto3

# Configure production logger for Amazon CloudWatch
logger = logging.getLogger("iot-simulator")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Initialize DynamoDB resource outside handler for connection reuse
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('TABLE_NAME', 'iot-telemetry')
table = dynamodb.Table(table_name)

DEVICES = [f"sensor-press-{i:03d}" for i in range(1, 6)]
DEVICE_TYPE = "hydraulic_press"


def lambda_handler(event, context):
    """
    HTTP-triggered Lambda to generate synthetic IoT telemetry records.
    Accepts JSON body or query parameters to control anomaly and error injection.
    """
    params = {}
    if isinstance(event, dict):
        if event.get('body'):
            try:
                params = json.loads(event['body'])
            except Exception as exc:
                logger.warning("Invalid JSON body received; falling back to defaults | error=%s", str(exc))
                params = {}
        elif event.get('queryStringParameters'):
            params = event.get('queryStringParameters') or {}

    count = int(params.get('count', 10))
    force_anomaly = bool(params.get('force_anomaly', False))
    force_error = bool(params.get('force_error', False))

    logger.info(
        "Starting telemetry simulation | count=%d | force_anomaly=%s | force_error=%s",
        count, force_anomaly, force_error
    )

    # Determine how many special records to inject (2 or 3 for a batch >= 10)
    target_count = min(random.randint(2, 3) if count >= 10 else 1, count)

    anomaly_indices = set(random.sample(range(count), target_count)) if force_anomaly else set()
    available_for_error = [idx for idx in range(count) if idx not in anomaly_indices]
    error_count = min(target_count, len(available_for_error))
    error_indices = set(random.sample(available_for_error, error_count)) if force_error else set()

    records_written = 0
    anomalies_created = 0
    errors_injected = 0
    batch_timestamp = datetime.now(timezone.utc).isoformat()

    try:
        with table.batch_writer() as batch:
            for i in range(count):
                device_id = random.choice(DEVICES)
                timestamp = datetime.now(timezone.utc).isoformat()
                telemetry_id = str(uuid.uuid4())

                # 1. Randomized Deliberate Schema Error (tests SQS DLQ)
                if i in error_indices:
                    item = {
                        'device_id': device_id,
                        'timestamp': timestamp,
                        'telemetry_id': telemetry_id,
                        'device_type': DEVICE_TYPE,
                        'temperature_c': "CORRUPTED_STRING_VALUE",  # Violates float schema in Lambda 2
                        'vibration_hz': Decimal("40.0"),
                        'pressure_psi': Decimal("100.0"),
                        'battery_pct': 80,
                        'status': 'ERROR'
                    }
                    errors_injected += 1
                    logger.warning(
                        "Injected schema error | index=%d | telemetry_id=%s | device_id=%s",
                        i, telemetry_id, device_id
                    )

                # 2. Randomized Critical Anomaly (tests SNS alert)
                elif i in anomaly_indices:
                    temp = Decimal(str(round(random.uniform(92.0, 115.0), 2)))
                    vib = Decimal(str(round(random.uniform(130.0, 180.0), 2)))
                    pressure = Decimal(str(round(random.uniform(115.0, 130.0), 1)))
                    item = {
                        'device_id': device_id,
                        'timestamp': timestamp,
                        'telemetry_id': telemetry_id,
                        'device_type': DEVICE_TYPE,
                        'temperature_c': temp,
                        'vibration_hz': vib,
                        'pressure_psi': pressure,
                        'battery_pct': random.randint(40, 80),
                        'status': 'ANOMALY'
                    }
                    anomalies_created += 1
                    logger.warning(
                        "Injected critical anomaly | index=%d | telemetry_id=%s | device_id=%s | temp=%s | vib=%s",
                        i, telemetry_id, device_id, str(temp), str(vib)
                    )

                # 3. Standard Telemetry (Happy Path)
                else:
                    temp = Decimal(str(round(random.uniform(55.0, 75.0), 2)))
                    vib = Decimal(str(round(random.uniform(20.0, 50.0), 2)))
                    pressure = Decimal(str(round(random.uniform(95.0, 105.0), 1)))
                    item = {
                        'device_id': device_id,
                        'timestamp': timestamp,
                        'telemetry_id': telemetry_id,
                        'device_type': DEVICE_TYPE,
                        'temperature_c': temp,
                        'vibration_hz': vib,
                        'pressure_psi': pressure,
                        'battery_pct': random.randint(50, 100),
                        'status': 'HEALTHY'
                    }

                batch.put_item(Item=item)
                records_written += 1

    except Exception as exc:
        logger.error("Failed writing telemetry batch to DynamoDB | table=%s | error=%s", table_name, str(exc))
        raise

    logger.info(
        "Simulation batch completed | table=%s | written=%d | anomalies=%d | errors=%d",
        table_name, records_written, anomalies_created, errors_injected
    )

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'message': 'Telemetry simulation completed successfully',
            'records_written': records_written,
            'anomalies_created': anomalies_created,
            'errors_injected': errors_injected,
            'batch_timestamp': batch_timestamp
        })
    }