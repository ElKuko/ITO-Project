#!/usr/bin/env python3
"""Generate cost presentation PDF for ITO Project using ReportLab."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Colors
BLUE = HexColor('#2980b9')
GREEN = HexColor('#27ae60')
DARK = HexColor('#2c3e50')
LIGHT_BLUE = HexColor('#ebf5fb')
GRAY = HexColor('#7f8c8d')

def create_pdf():
    doc = SimpleDocTemplate(
        'cost_forecast.pdf',
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=BLUE,
        alignment=TA_CENTER,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=GRAY,
        alignment=TA_CENTER,
        spaceAfter=30
    )

    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=DARK,
        spaceBefore=20,
        spaceAfter=10
    )

    note_style = ParagraphStyle(
        'Note',
        parent=styles['Normal'],
        fontSize=10,
        textColor=GRAY,
        leftIndent=15,
        spaceBefore=3
    )

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=GRAY,
        alignment=TA_CENTER,
        spaceBefore=30
    )

    elements = []

    # Title
    elements.append(Paragraph('ITO Merchandising App', title_style))
    elements.append(Paragraph('Cost Components & 3-Year Forecast', subtitle_style))

    # Section 1: Monthly Cost Components
    elements.append(Paragraph('Monthly Cost Components', section_style))

    cost_data = [
        ['Service', 'Description', 'Monthly Cost'],
        ['Railway (Compute + Database)', 'FastAPI + PostgreSQL', '$5 - $15'],
        ['Cloudflare R2 (Storage)', 'Shelf photo uploads', '$0 - $11'],
        ['Total Monthly Cost', '', '$5 - $26'],
    ]

    cost_table = Table(cost_data, colWidths=[2.8*inch, 2.2*inch, 1.5*inch])
    cost_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Body
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 10),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        # Total row
        ('BACKGROUND', (0, -1), (-1, -1), BLUE),
        ('TEXTCOLOR', (0, -1), (-1, -1), white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('SPAN', (0, -1), (1, -1)),
        ('ALIGN', (0, -1), (1, -1), 'RIGHT'),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(cost_table)

    elements.append(Spacer(1, 25))

    # Section 2: 3-Year Forecast
    elements.append(Paragraph('3-Year Cost Forecast', section_style))

    forecast_data = [
        ['Year', 'Railway', 'R2 Storage', 'Annual Total'],
        ['Year 1', '$5 - $15/mo', '$0 - $11/mo', '$60 - $312'],
        ['Year 2', '$5 - $15/mo', '$0 - $11/mo', '$60 - $312'],
        ['Year 3', '$5 - $15/mo', '$0 - $11/mo', '$60 - $312'],
        ['3-Year Total', '', '', '$180 - $936'],
    ]

    forecast_table = Table(forecast_data, colWidths=[1.5*inch, 1.6*inch, 1.6*inch, 1.8*inch])
    forecast_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Body
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 10),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('BACKGROUND', (0, 3), (-1, 3), LIGHT_BLUE),
        # Total row
        ('BACKGROUND', (0, -1), (-1, -1), GREEN),
        ('TEXTCOLOR', (0, -1), (-1, -1), white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('SPAN', (0, -1), (2, -1)),
        ('ALIGN', (0, -1), (2, -1), 'RIGHT'),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(forecast_table)

    elements.append(Spacer(1, 25))

    # Section 3: Cost Distribution
    elements.append(Paragraph('Cost Distribution (at max usage)', section_style))

    dist_data = [
        ['Component', 'Max Monthly', 'Share'],
        ['Railway (Compute + DB)', '$15', '58%'],
        ['R2 Storage', '$11', '42%'],
    ]

    dist_table = Table(dist_data, colWidths=[2.5*inch, 1.5*inch, 1.2*inch])
    dist_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), HexColor('#d6eaf8')),
        ('BACKGROUND', (0, 2), (-1, 2), HexColor('#d5f5e3')),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(dist_table)

    elements.append(Spacer(1, 25))

    # Section 4: Key Assumptions
    elements.append(Paragraph('Key Assumptions', section_style))

    notes = [
        'Railway includes FastAPI compute and managed PostgreSQL database',
        'R2 storage costs depend on volume of shelf photos uploaded',
        'R2 free tier includes 10GB storage and 10M requests/month',
        'Costs are projected to remain stable across years 1-3',
        'All estimates in USD based on current cloud provider pricing',
    ]

    for note in notes:
        elements.append(Paragraph(f'  {note}', note_style))

    # Footer
    elements.append(Paragraph(
        'ITO Merchandising App | Shelf Audit & Store Visit Management | Puerto Rico',
        footer_style
    ))

    doc.build(elements)
    print('PDF created: cost_forecast.pdf')
    print(f'Full path: /home/user/ITO-Project/cost_forecast.pdf')

if __name__ == '__main__':
    create_pdf()
