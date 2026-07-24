"""Deterministic executive PDF renderer for a completed ThreatLens analysis."""

from __future__ import annotations

from html import escape
from io import BytesIO


def _safe(value: object, limit: int = 1600) -> str:
    return escape(str(value if value is not None else "")[:limit])


def _plain(value: object, limit: int = 300) -> str:
    return str(value if value is not None else "")[:limit]


def _detection_alternative_rows(architecture: dict) -> list[list[str]]:
    rows = []
    for alternative in architecture.get("detectionAlternatives") or []:
        metadata = alternative.get("metadata") or {}
        rows.append([
            _plain(alternative.get("id")),
            _plain(alternative.get("name")),
            _plain(alternative.get("type")),
            _plain(alternative.get("provider", "generic")),
            f"{round(float(alternative.get('confidence', 0)) * 100)}%",
            _plain(metadata.get("supersededBy")),
            _plain(metadata.get("supersededReason") or "Not provided"),
        ])
    return rows


def generate_pdf(analysis: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ThreatLensTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=colors.HexColor("#0b3f42"), alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=colors.HexColor("#17202a"), spaceBefore=12, spaceAfter=7))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#526170")))
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title="ThreatLens AI STRIDE Report")
    story = []
    architecture = analysis.get("architecture") or {}
    threats = analysis.get("threats") or []
    comparison = analysis.get("riskComparison") or {"inherent": analysis.get("score", {}), "residual": analysis.get("score", {}), "reduction": 0, "counts": {}}
    story.extend([
        Paragraph("ThreatLens AI", styles["ThreatLensTitle"]),
        Paragraph("STRIDE Threat Modeling Report", styles["Heading2"]),
        Paragraph(f"Architecture: {_safe(architecture.get('name', 'Untitled architecture'))}", styles["BodyText"]),
        Spacer(1, 8),
    ])
    risk_data = [
        ["Inherent risk", "Residual risk", "Reduction", "Components", "Threats"],
        [
            f"{comparison['inherent'].get('value', 0)}/10",
            f"{comparison['residual'].get('value', 0)}/10",
            f"{comparison.get('reduction', 0)} pts",
            str(len(architecture.get("components") or [])),
            str(len(threats)),
        ],
    ]
    risk_table = Table(risk_data, colWidths=[34 * mm] * 5)
    risk_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9f1f3")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0b3f42")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5df")),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([risk_table, Paragraph("Executive summary", styles["Section"]), Paragraph(_safe(comparison["residual"].get("summary") or analysis.get("score", {}).get("summary") or "Security review required."), styles["BodyText"])])
    alternative_rows = _detection_alternative_rows(architecture)
    if alternative_rows:
        story.extend([
            Paragraph("Detection alternatives pending review", styles["Section"]),
            Paragraph(
                f"{len(alternative_rows)} superseded hypothesis(es), retained for review only and excluded from threats, graph, and risk.",
                styles["Small"],
            ),
        ])
        alternative_table = Table(
            [["ID", "Name", "Type", "Provider", "Confidence", "Superseded by", "Reason"]]
            + [
                [
                    Paragraph(_safe(row[0]), styles["Small"]),
                    Paragraph(_safe(row[1]), styles["Small"]),
                    row[2],
                    row[3],
                    row[4],
                    Paragraph(_safe(row[5]), styles["Small"]),
                    Paragraph(_safe(row[6]), styles["Small"]),
                ]
                for row in alternative_rows
            ],
            colWidths=[22 * mm, 30 * mm, 22 * mm, 18 * mm, 18 * mm, 28 * mm, 34 * mm],
            repeatRows=1,
        )
        alternative_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4f5")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5df")),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(alternative_table)
    story.append(Paragraph("Risk matrix", styles["Section"]))
    statuses = ["open", "mitigated", "accepted", "false_positive"]
    matrix = [["Severity", "Open", "Mitigated", "Accepted", "False positive"]]
    for severity in ("Critical", "High", "Medium", "Low"):
        matrix.append([severity, *[str(sum(1 for threat in threats if threat.get("severity") == severity and (threat.get("management") or {}).get("status", "open") == status)) for status in statuses]])
    matrix_table = Table(matrix, colWidths=[34 * mm] * 5)
    matrix_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#25313d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5df")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([matrix_table, Paragraph("Prioritized mitigation plan", styles["Section"])])
    mitigation_rows = [["Status", "Threat", "Owner", "Selected countermeasure"]]
    for threat in threats[:20]:
        management = threat.get("management") or {}
        selected = management.get("selectedCountermeasure") or (threat.get("countermeasures") or ["Pending selection"])[0]
        mitigation_rows.append([
            _plain(management.get("status", "open")), Paragraph(_safe(threat.get("title", "Threat")), styles["Small"]),
            _plain(management.get("owner") or "Unassigned"), Paragraph(_safe(selected), styles["Small"]),
        ])
    mitigation_table = Table(mitigation_rows, colWidths=[20 * mm, 55 * mm, 25 * mm, 70 * mm], repeatRows=1)
    mitigation_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9f1f3")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5df")),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([mitigation_table, Paragraph("Threat details and references", styles["Section"])])
    for index, threat in enumerate(threats[:20], start=1):
        management = threat.get("management") or {}
        story.append(Paragraph(_safe(f"{index}. {threat.get('severity')} | {threat.get('stride')} | {threat.get('title')}"), styles["Heading3"]))
        story.append(Paragraph(f"Evidence: {_safe(threat.get('evidence', 'Not available'))}", styles["Small"]))
        story.append(Paragraph(f"Treatment: {_safe(management.get('status', 'open'))} | Owner: {_safe(management.get('owner') or 'Unassigned')}", styles["Small"]))
        references = ", ".join(f"{_plain(item.get('id'))} ({_plain(item.get('framework'))})" for item in threat.get("securityReferences") or [])
        if references:
            story.append(Paragraph(f"References: {_safe(references)}", styles["Small"]))
        story.append(Spacer(1, 6))
    def add_footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5df"))
        canvas.line(16 * mm, 11 * mm, A4[0] - 16 * mm, 11 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#687484"))
        canvas.drawString(16 * mm, 7 * mm, "ThreatLens AI - offline deterministic report")
        canvas.drawRightString(A4[0] - 16 * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return buffer.getvalue()
