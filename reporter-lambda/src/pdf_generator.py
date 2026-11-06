import io
from fpdf import FPDF


class ExecutiveReportPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(35, 47, 62)  # AWS Navy
        self.cell(0, 10, 'Industrial IoT 24-Hour Executive Summary', border=False, new_x="LMARGIN", new_y="NEXT", align='L')
        self.set_draw_color(255, 153, 0)  # AWS Orange accent bar
        self.set_line_width(0.8)
        self.line(self.get_x(), self.get_y(), self.get_x() + 190, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | AWS Serverless IoT Pipeline Automated Report', align='C')


def generate_pdf_report(report_date, fleet_summary, incidents):
    """
    Compiles an executive summary PDF in memory.
    Returns bytes of the generated PDF file.
    """
    pdf = ExecutiveReportPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # 1. Report Metadata
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 6, f"Reporting Date: {report_date} (UTC) | Generated via Amazon Athena SQL", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # 2. Section 1: Fleet Operational Performance
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(35, 47, 62)
    pdf.cell(0, 8, "1. Fleet Operational Performance", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', '', 10)
    metrics = [
        ("Total Telemetry Readings Processed", fleet_summary.get("total_readings", "0")),
        ("Active Monitored Sensor Devices", fleet_summary.get("active_devices", "0")),
        ("Fleet Average Temperature", f"{fleet_summary.get('avg_temp', '0.0')} C"),
        ("Average Machine Health Score", f"{fleet_summary.get('avg_health', '100')}/100"),
        ("Flagged Critical / Warning Incidents", str(len(incidents))),
    ]

    for label, val in metrics:
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(110, 7, f"  {label}", border=1, fill=True)
        pdf.cell(80, 7, f"  {val}", border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # 3. Section 2: Incident Log for Date Window
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(35, 47, 62)
    pdf.cell(0, 8, "2. Incident Log for Date Window", new_x="LMARGIN", new_y="NEXT")

    if incidents:
        # Table Header
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(32, 6, "Timestamp", border=1, fill=True)
        pdf.cell(28, 6, "Device ID", border=1, fill=True)
        pdf.cell(20, 6, "Severity", border=1, fill=True)
        pdf.cell(18, 6, "Health", border=1, fill=True)
        pdf.cell(20, 6, "Temp (C)", border=1, fill=True)
        pdf.cell(22, 6, "Vib (Hz)", border=1, fill=True)
        pdf.cell(50, 6, "Facility", border=1, new_x="LMARGIN", new_y="NEXT", fill=True)

        # Table Rows
        pdf.set_font('Helvetica', '', 8)
        for inc in incidents:
            severity = inc.get("severity", "CRITICAL")
            if severity == "CRITICAL":
                pdf.set_text_color(200, 0, 0)
            else:
                pdf.set_text_color(200, 120, 0)

            pdf.cell(32, 6, str(inc.get('evaluated_at', ''))[:19], border=1)
            pdf.cell(28, 6, str(inc.get('device_id', '')), border=1)
            pdf.cell(20, 6, str(severity), border=1)
            pdf.cell(18, 6, f"{inc.get('health_score', '')}/100", border=1)
            pdf.cell(20, 6, str(inc.get('temperature_c', '')), border=1)
            pdf.cell(22, 6, str(inc.get('vibration_hz', '')), border=1)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(50, 6, str(inc.get('plant_location', '')), border=1, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 8, "  Zero critical incidents recorded in this 24-hour window.", border=1, new_x="LMARGIN", new_y="NEXT")

    buffer = io.BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()