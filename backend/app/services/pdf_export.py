from html import escape
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

def export_analysis_pdf(analysis:dict)->bytes:
    buffer=BytesIO()
    styles=getSampleStyleSheet()
    document=SimpleDocTemplate(buffer, pagesize=letter)

    story=[
        Paragraph(escape(analysis["company_name"]), styles["Title"]),
        Paragraph("10-K Analysis Report", styles["Heading2"]),
        Spacer(1, 12),
    ]

    sections = [
        ("Financial Overview", analysis["financial_overview"]),
        ("Company Development", analysis["company_development"]),
    ]

    for heading, text in sections:
        story.append(Paragraph(heading, styles["Heading1"]))

        for line in text.splitlines():
            line = line.strip()
            if line:
                story.append(Paragraph(escape(line.replace("**", "")), styles["BodyText"]))
                story.append(Spacer(1, 6))

        story.append(Spacer(1, 12))

    document.build(story)
    return buffer.getvalue()