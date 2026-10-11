"""Readable PDF exports, generated in memory without temporary server files."""

import io
import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer

# These fonts ship with ReportLab, so deployment needs no system fonts.
FONT_DIRECTORY = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("Cruciverba", str(FONT_DIRECTORY / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("CruciverbaBold", str(FONT_DIRECTORY / "VeraBd.ttf")))
ACCENT = colors.HexColor("#45614d")
TEXT = colors.HexColor("#253329")
MUTED = colors.HexColor("#69746d")


def export_filename(person_name, extension):
    safe_name = re.sub(r"[^a-z0-9_-]+", "_", person_name.lower()).strip("_") or "laurea"
    return f"cruciverba_{safe_name}.{extension}"


def _paragraph_text(value):
    # Contributions are plain text, never ReportLab markup or external resources.
    return escape(str(value)).replace("\n", "<br/>")


def _display_date(timestamp):
    try:
        return datetime.fromisoformat(timestamp).strftime("%d/%m/%Y alle %H:%M")
    except (TypeError, ValueError):
        return str(timestamp)


def _page_footer(canvas, document):
    canvas.saveState()
    canvas.setFont("Cruciverba", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, "Cruciverba di laurea")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Pagina {document.page}")
    canvas.restoreState()


def create_pdf_bytes(submissions, person_name):
    """Create an A4 document, keeping each word with its clue and contributor."""
    body = ParagraphStyle(
        "body", fontName="Cruciverba", fontSize=9.5, leading=13,
        textColor=TEXT, spaceAfter=3,
    )
    styles = {
        "body": body,
        "label": ParagraphStyle(
            "label", parent=body, fontName="CruciverbaBold", fontSize=8,
            leading=11, textColor=ACCENT, spaceAfter=6,
        ),
        "title": ParagraphStyle(
            "title", parent=body, fontName="CruciverbaBold", fontSize=20,
            leading=25, spaceAfter=8,
        ),
        "word": ParagraphStyle(
            "word", parent=body, fontName="CruciverbaBold", fontSize=11,
            leading=14, textColor=ACCENT, spaceAfter=2,
        ),
        "meta": ParagraphStyle(
            "meta", parent=body, fontSize=8, leading=10.5,
            textColor=MUTED, spaceAfter=3,
        ),
    }
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=22 * mm,
        title=f"Cruciverba di {person_name}",
        author="Cruciverba di laurea",
        pageCompression=1,
    )
    count = len(submissions)
    noun = "contributo" if count == 1 else "contributi"
    story = [
        Paragraph("PAROLE E INDIZI", styles["label"]),
        Paragraph(_paragraph_text(f"Cruciverba di {person_name}"), styles["title"]),
        Paragraph(
            f"{count} {noun}. Ogni parola è accompagnata dal suo indizio "
            "e da chi l'ha proposta.",
            styles["body"],
        ),
        Spacer(1, 4 * mm),
    ]
    if not submissions:
        story.append(Paragraph(
            "Nessun contributo ancora. Le parole inviate dagli invitati appariranno qui.",
            styles["body"],
        ))

    for number, submission in enumerate(submissions, start=1):
        contributor = submission["nome"] or "Anonimo"
        date = _display_date(submission["timestamp"])
        story.append(KeepTogether([
            Paragraph(
                _paragraph_text(f"{number:02d}. {submission['parola'].upper()}"),
                styles["word"],
            ),
            Paragraph(_paragraph_text(submission["frase_indizio"]), styles["body"]),
            Paragraph(
                _paragraph_text(f"Proposto da {contributor} | {date}"), styles["meta"],
            ),
            HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dce2dd")),
            Spacer(1, 1.5 * mm),
        ]))

    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return output.getvalue()
