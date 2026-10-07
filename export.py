from __future__ import annotations

import io
import json

from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def as_json(dilemma: str, category: str, response) -> bytes:
    return json.dumps({"dilemma": dilemma, "category": category, "response": response.model_dump()}, indent=2).encode()


def as_pdf(dilemma: str, category: str, response) -> bytes:
    out = io.BytesIO(); styles = getSampleStyleSheet()
    story = [Paragraph(f"Council — {category}", styles["Title"]), Paragraph(dilemma, styles["BodyText"]), Spacer(1, 10), Paragraph(f"Verdict: {response.verdict}", styles["BodyText"]), Paragraph(f"Confidence: {response.confidence:.0%}", styles["BodyText"])]
    for label in ("logic", "risk", "human", "growth"):
        perspective = getattr(response, label)
        story += [Spacer(1, 8), Paragraph(label.title(), styles["Heading2"]), Paragraph(f"{perspective.summary}<br/>{perspective.advice}<br/><i>Risk: {perspective.risk_note}</i>", styles["BodyText"])]
    story.append(Paragraph(f"Caution: {response.caution_note or 'None'}", styles["BodyText"]))
    SimpleDocTemplate(out, pagesize=LETTER, rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45).build(story)
    return out.getvalue()
