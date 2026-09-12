"""Presentation-ready PDF reports for page and site audit results."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#17201D")
MUTED = colors.HexColor("#66716D")
LINE = colors.HexColor("#DCE3DF")
WASH = colors.HexColor("#F5F7F6")
TEAL = colors.HexColor("#087B70")
RED = colors.HexColor("#B63434")
AMBER = colors.HexColor("#95600A")
BLUE = colors.HexColor("#2D5E91")
GREEN = colors.HexColor("#27734D")
SEVERITY_COLOR = {"critical": RED, "high": AMBER, "medium": BLUE, "low": MUTED}


def _text(value: Any, limit: int = 800) -> str:
    if isinstance(value, list):
        value = " | ".join(str(item) for item in value)
    rendered = str(value or "")
    if len(rendered) > limit:
        rendered = rendered[: limit - 3] + "..."
    return escape(rendered)


def _footer(canvas, document) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(16 * mm, 12 * mm, A4[0] - 16 * mm, 12 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(16 * mm, 8 * mm, "LocalLift evidence-grounded SEO audit")
    canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f"Page {document.page}")
    canvas.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "LLTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22,
            leading=27, textColor=INK, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "LLSubtitle", parent=base["Normal"], fontSize=9, leading=13,
            textColor=MUTED, spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "LLH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=14,
            leading=18, textColor=INK, spaceBefore=12, spaceAfter=8,
        ),
        "h3": ParagraphStyle(
            "LLH3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10,
            leading=13, textColor=INK, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "LLBody", parent=base["BodyText"], fontSize=8.5, leading=12,
            textColor=INK, spaceAfter=5, splitLongWords=True,
        ),
        "small": ParagraphStyle(
            "LLSmall", parent=base["BodyText"], fontSize=7.5, leading=10,
            textColor=MUTED, splitLongWords=True,
        ),
        "label": ParagraphStyle(
            "LLLabel", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7,
            leading=9, textColor=MUTED, spaceAfter=2,
        ),
        "severity": ParagraphStyle(
            "LLSeverity", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.5,
            leading=10, textColor=colors.white,
        ),
        "right": ParagraphStyle(
            "LLRight", parent=base["Normal"], fontSize=8, leading=11,
            textColor=MUTED, alignment=TA_RIGHT,
        ),
    }


def _metric_table(result: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    site_audit = result.get("audit_type") == "site"
    facts = result.get("facts", {})
    severity = result.get("issues", [{}])[0].get("severity", "clear") if result.get("issues") else "clear"
    fourth_label = "Pages analyzed" if site_audit else "Indexability"
    fourth_value = facts.get("pages_analyzed", 0) if site_audit else ("Indexable" if facts.get("indexable") else "Blocked")
    values = [
        ("READINESS", f"{result.get('score', 0)}/100"),
        ("TOP PRIORITY", severity.title()),
        ("ISSUE GROUPS" if site_audit else "OPEN ISSUES", len(result.get("issues", []))),
        (fourth_label.upper(), fourth_value),
    ]
    cells = [[
        Paragraph(f"<b>{_text(label)}</b><br/><font size='14'>{_text(value)}</font>", styles["body"])
        for label, value in values
    ]]
    table = Table(cells, colWidths=[42 * mm] * 4)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WASH),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table


def _issue_story(issue: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list[Any]:
    severity = str(issue.get("severity", "low")).casefold()
    count = issue.get("affected_count")
    suffix = f" ({count} page{'s' if count != 1 else ''})" if count else ""
    header = Table([[
        Paragraph(_text(severity.upper()), styles["severity"]),
        Paragraph(f"<b>{_text(issue.get('title'))}{_text(suffix)}</b>", styles["body"]),
    ]], colWidths=[24 * mm, 144 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), SEVERITY_COLOR.get(severity, MUTED)),
        ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
        ("BACKGROUND", (1, 0), (1, 0), WASH),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    detail = Table([
        [Paragraph("<b>EVIDENCE</b>", styles["label"]), Paragraph("<b>RECOMMENDED ACTION</b>", styles["label"])],
        [Paragraph(_text(issue.get("evidence"), 500), styles["small"]), Paragraph(_text(issue.get("recommendation"), 500), styles["small"])],
    ], colWidths=[84 * mm, 84 * mm])
    detail.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [header, detail, Spacer(1, 4 * mm)]


def _page_inventory(pages: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [[
        Paragraph("<b>Score</b>", styles["small"]),
        Paragraph("<b>Type</b>", styles["small"]),
        Paragraph("<b>Page</b>", styles["small"]),
        Paragraph("<b>Issues</b>", styles["small"]),
        Paragraph("<b>Indexable</b>", styles["small"]),
    ]]
    for page in pages:
        rows.append([
            Paragraph(_text(page.get("score")), styles["small"]),
            Paragraph(_text(page.get("page_type", "").title()), styles["small"]),
            Paragraph(_text(page.get("facts", {}).get("title") or page.get("url"), 180), styles["small"]),
            Paragraph(_text(len(page.get("issues", []))), styles["small"]),
            Paragraph("Yes" if page.get("facts", {}).get("indexable") else "No", styles["small"]),
        ])
    table = Table(rows, colWidths=[15 * mm, 23 * mm, 100 * mm, 15 * mm, 20 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, WASH]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def build_pdf(result: dict[str, Any]) -> bytes:
    if not isinstance(result, dict) or not isinstance(result.get("site"), dict):
        raise ValueError("A complete audit result is required for PDF export.")
    styles = _styles()
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=f"LocalLift Audit - {result['site'].get('business_name', 'Business')}",
        author="LocalLift",
    )
    site = result["site"]
    scope = "Site crawl" if result.get("audit_type") == "site" else "Single page"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story: list[Any] = [
        Table([[
            Paragraph("<font color='#087B70'><b>LOCALLIFT</b></font><br/><font size='8'>LOCAL SEO TRIAGE</font>", styles["body"]),
            Paragraph(f"{_text(scope)}<br/>{_text(generated)}", styles["right"]),
        ]], colWidths=[84 * mm, 84 * mm]),
        Spacer(1, 8 * mm),
        Paragraph(_text(site.get("business_name")), styles["title"]),
        Paragraph(
            f"{_text(site.get('city'))} | {_text(site.get('service') or 'All applicable pages')}<br/>"
            f"{_text(site.get('url'))}", styles["subtitle"],
        ),
        _metric_table(result, styles),
        Spacer(1, 4 * mm),
    ]

    ai = result.get("ai", {})
    if ai.get("status") == "complete":
        story.extend([
            Paragraph("Executive summary", styles["h2"]),
            Paragraph(_text(ai.get("result", {}).get("executive_summary"), 1800), styles["body"]),
        ])

    story.append(Paragraph("Prioritized findings", styles["h2"]))
    issues = result.get("issues", [])[:30]
    if issues:
        for issue in issues:
            story.extend(_issue_story(issue, styles))
    else:
        story.append(Paragraph("No material issue was found by the automated checks.", styles["body"]))

    pages = result.get("pages", [])
    if pages:
        story.extend([PageBreak(), Paragraph("Page inventory", styles["h2"]), _page_inventory(pages, styles)])

    if ai.get("status") == "complete":
        ai_result = ai.get("result", {})
        checks = ai_result.get("human_checks", [])
        story.extend([Paragraph("Human verification queue", styles["h2"])])
        if checks:
            for item in checks:
                story.append(Paragraph(f"- {_text(item, 500)}", styles["body"]))
        story.extend([
            Paragraph("AI boundary", styles["h2"]),
            Paragraph(_text(ai_result.get("scale_note"), 1000), styles["body"]),
        ])

    story.extend([
        Paragraph("Method note", styles["h2"]),
        Paragraph(
            "The readiness score is a triage heuristic, not a Google ranking score. Static HTML checks do "
            "not verify Search Console, GBP, rankings, reviews, backlinks, conversions, field Core Web Vitals, "
            "or clinical claims. Human verification remains required.", styles["small"],
        ),
    ])
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()
