class ValidationError(Exception):
    """Raised when a telemetry record fails schema validation."""
    pass


REQUIRED_FIELDS = ("device_id", "timestamp", "telemetry_id", "temperature_c", "vibration_hz")


def validate_telemetry_record(record):
    """
    Validates data types and structure of an enriched telemetry record.
    Returns cleaned record with validated numeric floats.
    Raises ValidationError if required fields are missing or types are corrupted.
    """
    if not isinstance(record, dict):
        raise ValidationError("Record payload must be a JSON object")

    for field in REQUIRED_FIELDS:
        if field not in record:
            raise ValidationError(f"Missing required field: {field}")

    # Explicit type checks: must be castable to float/int
    try:
        temp = float(record['temperature_c'])
        vib = float(record['vibration_hz'])
        pressure = float(record.get('pressure_psi', 100.0))
        battery = int(record.get('battery_pct', 100))
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"Data type corruption detected: {str(exc)}")

    # Reject non-sensical physical ranges
    if temp < -50.0 or temp > 250.0:
        raise ValidationError(f"Temperature {temp} C out of physical sensor bounds (-50 to 250 C)")
    if vib < 0.0 or vib > 500.0:
        raise ValidationError(f"Vibration {vib} Hz out of physical sensor bounds (0 to 500 Hz)")
    if battery < 0 or battery > 100:
        raise ValidationError(f"Battery {battery}% out of bounds (0 to 100%)")

    record_clean = dict(record)
    record_clean['temperature_c'] = temp
    record_clean['vibration_hz'] = vib
    record_clean['pressure_psi'] = pressure
    record_clean['battery_pct'] = battery

    return record_clean