#!/usr/bin/env python3
"""Generate cost presentation PDF for ITO Project using ReportLab."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER

# Colors
BLUE = HexColor('#2980b9')
GREEN = HexColor('#27ae60')
DARK = HexColor('#2c3e50')
LIGHT_BLUE = HexColor('#ebf5fb')
LIGHT_GREEN = HexColor('#d5f5e3')
GRAY = HexColor('#7f8c8d')
ORANGE = HexColor('#e67e22')

def create_pdf():
    doc = SimpleDocTemplate(
        'cost_forecast.pdf',
        pagesize=letter,
        rightMargin=0.6*inch,
        leftMargin=0.6*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'],
        fontSize=24, textColor=BLUE, alignment=TA_CENTER, spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'],
        fontSize=12, textColor=GRAY, alignment=TA_CENTER, spaceAfter=15
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Heading2'],
        fontSize=14, textColor=DARK, spaceBefore=15, spaceAfter=8
    )
    note_style = ParagraphStyle(
        'Note', parent=styles['Normal'],
        fontSize=9, textColor=GRAY, leftIndent=10, spaceBefore=2
    )
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceBefore=15
    )

    elements = []

    # Title
    elements.append(Paragraph('ITO Merchandising App', title_style))
    elements.append(Paragraph('Infrastructure Cost Forecast', subtitle_style))

    # =====================
    # ASSUMPTIONS
    # =====================
    elements.append(Paragraph('Assumptions', section_style))

    assumptions_data = [
        ['Parameter', 'Value', 'Notes'],
        ['Daily image uploads', '300 images', 'Shelf photos from store visits'],
        ['Active users', '6-8 users', 'Merchandisers in the field'],
        ['Operating days', '22 days/month', 'Business days only'],
        ['Usage hours', 'Business hours', '~10 hrs/day active usage'],
        ['Image size (compressed)', '~450 KB', 'JPEG @ 1280px max width'],
        ['Monthly storage growth', '~3 GB/month', '300 x 22 x 450KB'],
    ]

    assumptions_table = Table(assumptions_data, colWidths=[1.8*inch, 1.4*inch, 3*inch])
    assumptions_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('BACKGROUND', (0, 3), (-1, 3), LIGHT_BLUE),
        ('BACKGROUND', (0, 5), (-1, 5), LIGHT_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(assumptions_table)

    # =====================
    # CLOUDFLARE R2 COSTS
    # =====================
    elements.append(Paragraph('Cloudflare R2 Storage Costs', section_style))

    r2_data = [
        ['Component', 'Rate', 'Year 1', 'Year 2', 'Year 3'],
        ['Storage (cumulative)', '$0.015/GB/mo', '~36 GB', '~72 GB', '~108 GB'],
        ['Storage cost', '10 GB free', '$0.39/mo avg', '$0.93/mo avg', '$1.47/mo avg'],
        ['Class A ops (uploads)', '$4.50/1M', 'Free tier', 'Free tier', 'Free tier'],
        ['Class B ops (reads)', '$0.36/1M', 'Free tier', 'Free tier', 'Free tier'],
        ['Egress bandwidth', 'FREE', '$0', '$0', '$0'],
        ['Annual R2 Total', '', '$5', '$11', '$18'],
    ]

    r2_table = Table(r2_data, colWidths=[1.6*inch, 1.2*inch, 1.1*inch, 1.1*inch, 1.1*inch])
    r2_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f39c12')),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('BACKGROUND', (0, 3), (-1, 3), LIGHT_BLUE),
        ('BACKGROUND', (0, 5), (-1, 5), LIGHT_BLUE),
        ('BACKGROUND', (0, -1), (-1, -1), ORANGE),
        ('TEXTCOLOR', (0, -1), (-1, -1), white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(r2_table)

    r2_notes = [
        'Free tier: 10GB storage, 1M Class A ops, 10M Class B ops/month',
        'Class A = uploads/writes (~6,600/mo); Class B = reads/views (~20,000/mo) - both well under free limits',
    ]
    for note in r2_notes:
        elements.append(Paragraph(f'* {note}', note_style))

    # =====================
    # RAILWAY COSTS
    # =====================
    elements.append(Paragraph('Railway Compute + Database Costs', section_style))

    railway_data = [
        ['Component', 'Rate', 'Year 1', 'Year 2', 'Year 3'],
        ['FastAPI compute', '$0.028/vCPU-hr + $0.014/GB-hr', '~$8/mo', '~$10/mo', '~$12/mo'],
        ['PostgreSQL DB', 'Same rates + storage', '~$10/mo', '~$12/mo', '~$15/mo'],
        ['DB storage', '$0.25/GB/mo', '~$1/mo', '~$2/mo', '~$3/mo'],
        ['Network egress', '$0.10/GB', '~$1/mo', '~$1/mo', '~$2/mo'],
        ['Monthly Railway Total', '', '$20/mo', '$25/mo', '$32/mo'],
        ['Annual Railway Total', '', '$240', '$300', '$384'],
    ]

    railway_table = Table(railway_data, colWidths=[1.6*inch, 2.0*inch, 0.85*inch, 0.85*inch, 0.85*inch])
    railway_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('BACKGROUND', (0, 3), (-1, 3), LIGHT_BLUE),
        ('BACKGROUND', (0, -2), (-1, -2), HexColor('#d6eaf8')),
        ('FONTNAME', (0, -2), (-1, -2), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), BLUE),
        ('TEXTCOLOR', (0, -1), (-1, -1), white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(railway_table)

    railway_notes = [
        'Containers run 24/7 even during off-hours (720 hrs/mo)',
        'Estimate: 0.25 vCPU avg, 512MB RAM for API; similar for PostgreSQL',
        'Growth assumes modest increase in data/traffic over time',
    ]
    for note in railway_notes:
        elements.append(Paragraph(f'* {note}', note_style))

    # =====================
    # TOTAL SUMMARY
    # =====================
    elements.append(Paragraph('3-Year Cost Summary', section_style))

    summary_data = [
        ['', 'Year 1', 'Year 2', 'Year 3', '3-Year Total'],
        ['Railway (Compute + DB)', '$240', '$300', '$384', '$924'],
        ['Cloudflare R2 (Storage)', '$5', '$11', '$18', '$34'],
        ['Annual Total', '$245', '$311', '$402', '$958'],
        ['Monthly Average', '$20/mo', '$26/mo', '$34/mo', '$27/mo avg'],
    ]

    summary_table = Table(summary_data, colWidths=[2*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('BACKGROUND', (0, 2), (-1, 2), LIGHT_GREEN),
        ('BACKGROUND', (0, 3), (-1, 3), GREEN),
        ('TEXTCOLOR', (0, 3), (-1, 3), white),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
        ('FONTNAME', (-1, 1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (-1, 3), (-1, 3), HexColor('#1e8449')),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)

    elements.append(Spacer(1, 15))

    # Key insights
    elements.append(Paragraph('Key Insights', section_style))
    insights = [
        'Railway (compute + DB) is 97% of costs; R2 storage is negligible due to free tier + no egress fees',
        'Costs grow ~30%/year as data accumulates and modest resource scaling',
        'R2 free tier covers operations; only pay for storage above 10GB',
        'Consider: Railway sleep/wake for off-hours could reduce compute by ~60%',
    ]
    for insight in insights:
        elements.append(Paragraph(f'> {insight}', note_style))

    # Footer
    elements.append(Paragraph(
        'ITO Merchandising App | Puerto Rico | Generated March 2026',
        footer_style
    ))

    doc.build(elements)
    print('PDF created: cost_forecast.pdf')

if __name__ == '__main__':
    create_pdf()
