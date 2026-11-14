import os
import json
from decimal import Decimal
from boto3.dynamodb.types import TypeDeserializer

deserializer = TypeDeserializer()

# Parse plant metadata once at module load time for reuse across all batch records
_METADATA_MAP = json.loads(os.environ.get("PLANT_METADATA_JSON", "{}"))


def unmarshal_dynamodb_image(dynamodb_image):
    """Converts DynamoDB Stream typed dictionary into standard Python primitives."""
    clean_item = {}
    for key, value in dynamodb_image.items():
        val = deserializer.deserialize(value)
        if isinstance(val, Decimal):
            val = int(val) if val % 1 == 0 else float(val)
        clean_item[key] = val
    return clean_item


def get_asset_metadata(device_id):
    """
    Looks up the plant and maintenance team for the given device_id.
    Uses the module-level _METADATA_MAP parsed once at cold start from
    the PLANT_METADATA_JSON environment variable — avoids redundant
    json.loads() on every record in a batch.
    """
    return _METADATA_MAP.get(device_id, {"plant": "Unknown-Facility", "team": "Unassigned"})


def evaluate_machine_health(record):
    """
    Calculates a composite 0-100 Machine Health Score and classifies severity.
    Returns UNVALIDATED if schema types are corrupted so downstream Lambda 2
    can reject the payload into the SQS Dead-Letter Queue.
    """
    try:
        temp = float(record.get('temperature_c'))
        vib = float(record.get('vibration_hz'))
        pressure = float(record.get('pressure_psi', 100.0))
        battery = int(record.get('battery_pct', 100))
    except (ValueError, TypeError):
        return {
            "health_score": -1,
            "severity": "UNVALIDATED",
            "is_incident": False,
            "anomaly_reasons": ["SCHEMA_VALIDATION_DEFERRED_TO_ARCHIVER"]
        }

    score = 100
    reasons = []

    # 1. Temperature Thresholds (Critical > 85C, Warning > 78C)
    if temp > 85.0:
        score -= 45
        reasons.append(f"CRITICAL_OVERHEAT: Temperature ({temp} C) exceeded 85.0 C limit.")
    elif temp > 78.0:
        score -= 20
        reasons.append(f"ELEVATED_TEMPERATURE: Temperature ({temp} C) exceeded 78.0 C warning level.")

    # 2. Vibration Thresholds (Critical > 120Hz, Warning > 80Hz)
    if vib > 120.0:
        score -= 40
        reasons.append(f"SEVERE_VIBRATION: Vibration ({vib} Hz) exceeded 120.0 Hz limit.")
    elif vib > 80.0:
        score -= 15
        reasons.append(f"HIGH_VIBRATION: Vibration ({vib} Hz) exceeded 80.0 Hz warning level.")

    # 3. Pressure Thresholds (Nominal: 85 - 115 PSI)
    if pressure > 115.0 or pressure < 85.0:
        score -= 10
        reasons.append(f"PRESSURE_VARIANCE: Pressure ({pressure} PSI) outside 85-115 PSI band.")

    # 4. Battery Threshold (Warning < 25%)
    if battery < 25:
        score -= 10
        reasons.append(f"LOW_BATTERY: Sensor battery at {battery}%.")

    score = max(0, score)

    if score < 50:
        severity = "CRITICAL"
    elif score < 80:
        severity = "WARNING"
    else:
        severity = "NORMAL"

    return {
        "health_score": score,
        "severity": severity,
        "is_incident": severity in ("CRITICAL", "WARNING"),
        "anomaly_reasons": reasons
    }