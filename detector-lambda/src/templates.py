INCIDENT_TICKET_TEMPLATE = """====================================================================
                 🚨 INDUSTRIAL IOT INCIDENT TICKET 🚨
====================================================================

INCIDENT SUMMARY
--------------------------------------------------------------------
Severity Level   : {severity}
Health Score     : {health_score} / 100
Incident ID      : {telemetry_id}
Detected At      : {evaluated_at}

ASSET METADATA
--------------------------------------------------------------------
Device ID        : {device_id}
Equipment Type   : {device_type}
Facility         : {plant_location}
Assigned Team    : {maintenance_team}

TELEMETRY DIAGNOSTICS
--------------------------------------------------------------------
* Temperature    : {temperature_c} C    [MAX LIMIT: 85.0 C]
* Vibration      : {vibration_hz} Hz   [MAX LIMIT: 120.0 Hz]
* Pressure       : {pressure_psi} PSI  [NORMAL RANGE: 85.0 - 115.0 PSI]
* Battery Level  : {battery_pct} %

TRIGGERED VIOLATIONS
--------------------------------------------------------------------
{reasons_formatted}

RECOMMENDED ACTION
--------------------------------------------------------------------
Immediate inspection required on {device_id}. High risk of
thermal seizure or hydraulic seal failure.
====================================================================
"""


def build_incident_subject(record):
    """Generates a concise subject line within AWS SNS's 100-character limit."""
    subject = (
        f"[{record['severity']} ALERT] IoT Machine Fault | "
        f"{record.get('device_id', 'Unknown')} (Health: {record['health_score']}/100)"
    )
    return subject[:100]


def format_incident_ticket(record):
    """Populates the incident ticket template with enriched telemetry data."""
    reasons_list = record.get('anomaly_reasons', [])
    reasons_formatted = "\n".join(
        f"{idx}. {reason}" for idx, reason in enumerate(reasons_list, start=1)
    ) or "None"

    return INCIDENT_TICKET_TEMPLATE.format(
        severity=record.get('severity', 'UNKNOWN'),
        health_score=record.get('health_score', 'N/A'),
        telemetry_id=record.get('telemetry_id', 'N/A'),
        evaluated_at=record.get('evaluated_at', 'N/A'),
        device_id=record.get('device_id', 'Unknown'),
        device_type=record.get('device_type', 'hydraulic_press'),
        plant_location=record.get('plant_location', 'Unknown'),
        maintenance_team=record.get('maintenance_team', 'Unknown'),
        temperature_c=record.get('temperature_c', 'N/A'),
        vibration_hz=record.get('vibration_hz', 'N/A'),
        pressure_psi=record.get('pressure_psi', 'N/A'),
        battery_pct=record.get('battery_pct', 'N/A'),
        reasons_formatted=reasons_formatted
    )