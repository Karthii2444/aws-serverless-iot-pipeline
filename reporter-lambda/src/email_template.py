def render_executive_report_html(report_date, fleet_summary, incidents):
    """Renders a responsive, styled executive summary email report."""
    total_readings = fleet_summary.get("total_readings", "0")
    active_devices = fleet_summary.get("active_devices", "0")
    avg_temp = fleet_summary.get("avg_temp", "0.0")
    avg_health = fleet_summary.get("avg_health", "100")
    incident_count = len(incidents)

    # Build incident table rows
    if incidents:
        incident_rows = ""
        for inc in incidents:
            severity = inc.get("severity", "CRITICAL")
            color = "#d9534f" if severity == "CRITICAL" else "#f0ad4e"
            incident_rows += f"""
            <tr>
              <td style="padding: 8px; border: 1px solid #ddd;">{inc.get('evaluated_at', 'N/A')}</td>
              <td style="padding: 8px; border: 1px solid #ddd;"><strong>{inc.get('device_id', 'N/A')}</strong></td>
              <td style="padding: 8px; border: 1px solid #ddd; color: {color}; font-weight: bold;">{severity}</td>
              <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{inc.get('health_score', 'N/A')}/100</td>
              <td style="padding: 8px; border: 1px solid #ddd;">{inc.get('temperature_c', 'N/A')} &deg;C</td>
              <td style="padding: 8px; border: 1px solid #ddd;">{inc.get('vibration_hz', 'N/A')} Hz</td>
              <td style="padding: 8px; border: 1px solid #ddd;">{inc.get('plant_location', 'N/A')}</td>
            </tr>
            """
        incidents_table = f"""
        <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px;">
          <thead>
            <tr style="background-color: #f7f7f7; text-align: left;">
              <th style="padding: 8px; border: 1px solid #ddd;">Timestamp</th>
              <th style="padding: 8px; border: 1px solid #ddd;">Device</th>
              <th style="padding: 8px; border: 1px solid #ddd;">Severity</th>
              <th style="padding: 8px; border: 1px solid #ddd;">Health</th>
              <th style="padding: 8px; border: 1px solid #ddd;">Temp</th>
              <th style="padding: 8px; border: 1px solid #ddd;">Vibration</th>
              <th style="padding: 8px; border: 1px solid #ddd;">Facility</th>
            </tr>
          </thead>
          <tbody>
            {incident_rows}
          </tbody>
        </table>
        """
    else:
        incidents_table = """
        <p style="padding: 12px; background-color: #dff0d8; color: #3c763d; border-radius: 4px;">
          ✓ Zero critical incidents recorded in this 24-hour window. All factory machines operated within tolerance.
        </p>
        """

    return f"""
    <!DOCTYPE html>
    <html>
      <body style="font-family: Arial, sans-serif; color: #232f3e; line-height: 1.5; padding: 20px;">
        <h2 style="color: #232f3e; border-bottom: 2px solid #ff9900; padding-bottom: 8px;">
          🏭 Industrial IoT 24-Hour Executive Summary
        </h2>
        <p><strong>Reporting Date:</strong> {report_date} (UTC)</p>

        <h3>1. Fleet Operational Performance</h3>
        <table style="width: 100%; max-width: 500px; border-collapse: collapse; margin-bottom: 25px;">
          <tr style="background-color: #f7f7f7;"><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Telemetry Processed</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{total_readings}</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Active Monitored Sensors</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{active_devices}</td></tr>
          <tr style="background-color: #f7f7f7;"><td style="padding: 8px; border: 1px solid #ddd;"><strong>Fleet Average Temperature</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{avg_temp} &deg;C</td></tr>
          <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Average Machine Health Score</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{avg_health}/100</td></tr>
          <tr style="background-color: #f7f7f7;"><td style="padding: 8px; border: 1px solid #ddd;"><strong>Flagged Incidents</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: {'red' if incident_count > 0 else 'green'}; font-weight: bold;">{incident_count}</td></tr>
        </table>

        <h3>2. Incident Log for Date Window</h3>
        {incidents_table}

        <p style="font-size: 11px; color: #777; margin-top: 30px; border-top: 1px solid #eee; padding-top: 8px;">
          Generated automatically by AWS Serverless IoT Pipeline (Lambda 3 & Athena SQL).
        </p>
      </body>
    </html>
    """