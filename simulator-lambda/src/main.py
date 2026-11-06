import os
import json
import random
import uuid
from datetime import datetime, timezone
import boto3

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
            except Exception:
                params = {}
        elif event.get('queryStringParameters'):
            params = event.get('queryStringParameters') or {}

    count = int(params.get('count', 10))
    force_anomaly = bool(params.get('force_anomaly', False))
    force_error = bool(params.get('force_error', False))

    records_written = 0
    anomalies_created = 0
    errors_injected = 0
    batch_timestamp = datetime.now(timezone.utc).isoformat()

    with table.batch_writer() as batch:
        for i in range(count):
            device_id = random.choice(DEVICES)
            timestamp = datetime.now(timezone.utc).isoformat()
            telemetry_id = str(uuid.uuid4())

            # 1. Deliberate Schema Error (tests downstream SQS DLQ)
            if force_error and i == 0:
                item = {
                    'device_id': device_id,
                    'timestamp': timestamp,
                    'telemetry_id': telemetry_id,
                    'device_type': DEVICE_TYPE,
                    'temperature_c': "CORRUPTED_STRING_VALUE",  # Violates float schema in Lambda 2
                    'vibration_hz': 40.0,
                    'pressure_psi': 100.0,
                    'battery_pct': 80,
                    'status': 'ERROR'
                }
                errors_injected += 1

            # 2. Critical Anomaly (tests downstream SNS real-time alert)
            elif force_anomaly and i == 0:
                item = {
                    'device_id': device_id,
                    'timestamp': timestamp,
                    'telemetry_id': telemetry_id,
                    'device_type': DEVICE_TYPE,
                    'temperature_c': round(random.uniform(92.0, 115.0), 2),  # > 85.0 C threshold
                    'vibration_hz': round(random.uniform(130.0, 180.0), 2),  # > 120.0 Hz threshold
                    'pressure_psi': 118.0,
                    'battery_pct': 74,
                    'status': 'ANOMALY'
                }
                anomalies_created += 1

            # 3. Standard Telemetry (Happy Path)
            else:
                item = {
                    'device_id': device_id,
                    'timestamp': timestamp,
                    'telemetry_id': telemetry_id,
                    'device_type': DEVICE_TYPE,
                    'temperature_c': round(random.uniform(55.0, 75.0), 2),
                    'vibration_hz': round(random.uniform(20.0, 50.0), 2),
                    'pressure_psi': round(random.uniform(95.0, 105.0), 1),
                    'battery_pct': random.randint(50, 100),
                    'status': 'HEALTHY'
                }

            batch.put_item(Item=item)
            records_written += 1

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