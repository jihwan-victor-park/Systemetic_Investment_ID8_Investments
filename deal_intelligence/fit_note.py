"""Stage 1 fit note, organized by COMPANY (not by one-off screen).

A company is a durable thing — the same company can be screened again at a later
round — so each company gets one hub page keyed by a stable id (slug) + website,
and that page accumulates a dated screen history, newest first. Re-screening a
company prepends a new dated entry rather than overwriting the page.

Renders the same DealFit/DealInput data two ways: a branded .docx (latest screen,
for download/sharing) and a Docusaurus markdown page (the full company record).
ID8 "Latent Order" palette — Roboto Serif display, Sora body, charcoal #1A1A1A,
hairline tables — matching design/lib.js and the investment-memo builder.
"""
import os
import re
from datetime import date

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from . import rubric
from .schemas import DealFit, DealInput

C_CHARCOAL = RGBColor(0x1A, 0x1A, 0x1A)
C_GREY = RGBColor(0x82, 0x82, 0x82)
C_SOFT = RGBColor(0x3C, 0x3C, 0x3C)
HAIR_HEX = "E4DFD5"
FONT_HEAD = "Roboto Serif"
FONT_BODY = "Sora"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGO = os.path.join(_REPO_ROOT, "design", "assets", "id8_charcoal.png")

PARAM_LABELS = {p["key"]: p["label"] for p in rubric.PARAMS}
TIER_LABEL = {"very_high": "Very High Quality", "high": "High Quality", "below_threshold": "Below Threshold"}

_SCREENS_START = "<!-- SCREENS:START -->"
_SCREENS_END = "<!-- SCREENS:END -->"


def company_id(deal: DealInput) -> str:
    """Stable per-company id. Prefer the website domain (durable across rounds);
    fall back to a slug of the name."""
    domain = normalize_domain(deal.domain)
    if domain:
        return re.sub(r"[^a-z0-9]+", "-", domain.split(".")[0].lower()).strip("-")
    return slugify(deal.name)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def normalize_domain(domain: str) -> str:
    """www.assorthealth.com / https://assorthealth.com/ -> assorthealth.com"""
    if not domain:
        return ""
    d = re.sub(r"^https?://", "", domain.strip(), flags=re.I)
    d = re.sub(r"^www\.", "", d, flags=re.I)
    return d.rstrip("/").lower()


def _context_bits(deal: DealInput) -> list:
    return [b for b in (deal.round, deal.hq, deal.lead_investors) if b]


# ── DOCX ──────────────────────────────────────────────────────────────────────
def _run(paragraph, text, font=FONT_BODY, size=10.5, color=C_CHARCOAL, bold=False, all_caps=False):
    r = paragraph.add_run(text)
    r.font.name = font
    r.font.size = Pt(size)
    r.font.color.rgb = color
    r.bold = bold
    r.font.all_caps = all_caps
    return r


def _md_runs(paragraph, text, size=10.5, color=C_CHARCOAL):
    """Add runs to a paragraph, rendering Perplexity's markdown **bold** as real
    bold runs instead of showing literal asterisks."""
    for part in re.split(r"(\*\*.+?\*\*)", str(text or "")):
        if len(part) > 4 and part.startswith("**") and part.endswith("**"):
            _run(paragraph, part[2:-2], size=size, color=color, bold=True)
        elif part:
            _run(paragraph, part, size=size, color=color)


def _cell_bottom_border(cell, color=HAIR_HEX, size=4):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:color"), color)
    borders.append(bottom)
    tcPr.append(borders)


def _hairline_under(paragraph, color="1A1A1A", size=6):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:color"), color)
    bottom.set(qn("w:space"), "4")
    pBdr.append(bottom)
    pPr.append(pBdr)


def build_docx(fit: DealFit, deal: DealInput, output_path: str):
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(0.75)
    section.left_margin = section.right_margin = Inches(0.9)

    normal = doc.styles["Normal"]
    normal.font.name = FONT_BODY
    normal.font.size = Pt(10.5)

    title_p = doc.add_paragraph()
    _run(title_p, deal.name, font=FONT_HEAD, size=24, bold=True)

    domain = normalize_domain(deal.domain)
    sub_parts = _context_bits(deal)
    if domain:
        sub_parts = [domain] + sub_parts
    if sub_parts:
        sub_p = doc.add_paragraph()
        sub_p.paragraph_format.space_after = Pt(4)
        _run(sub_p, "   ·   ".join(sub_parts), size=11, color=C_GREY)

    hr_p = doc.add_paragraph()
    hr_p.paragraph_format.space_after = Pt(16)
    _hairline_under(hr_p)

    score_p = doc.add_paragraph()
    score_p.paragraph_format.space_after = Pt(10)
    _run(score_p, f"Fit score {fit.fit_score:.1f} / 4.0", font=FONT_HEAD, size=15, bold=True)
    tier = TIER_LABEL.get(fit.quality_tier, fit.quality_tier)
    gate_text = f"   —   CLEARS GATE  ·  {tier.upper()}" if fit.gate else "   —   BELOW THRESHOLD"
    _run(score_p, gate_text, size=10.5, color=C_GREY)

    table = doc.add_table(rows=1, cols=3)
    table.autofit = False
    widths = [Inches(1.9), Inches(0.6), Inches(4.4)]
    headers = table.rows[0].cells
    for i, label in enumerate(["Dimension", "Score", "Evidence"]):
        headers[i].width = widths[i]
        _run(headers[i].paragraphs[0], label, size=8.5, bold=True, all_caps=True, color=C_CHARCOAL)
        _cell_bottom_border(headers[i], color="1A1A1A", size=8)

    for param in fit.params:
        row = table.add_row().cells
        for c, w in zip(row, widths):
            c.width = w
        _run(row[0].paragraphs[0], PARAM_LABELS.get(param.key, param.key), size=9.5)
        _run(row[1].paragraphs[0], f"{param.score:.0f}", size=9.5)
        _md_runs(row[2].paragraphs[0], param.evidence, size=9, color=C_SOFT)
        for c in row:
            _cell_bottom_border(c)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    rat_head = doc.add_paragraph()
    _run(rat_head, "RATIONALE", size=8.5, bold=True, color=C_GREY, all_caps=True)
    rat_p = doc.add_paragraph()
    rat_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    rat_p.paragraph_format.space_after = Pt(18)
    _md_runs(rat_p, fit.rationale, size=10.5)

    foot_p = doc.add_paragraph()
    _run(foot_p, f"Confidence: {fit.confidence}   ·   Screened {date.today().isoformat()}   ·   "
                 f"ID8 Investments — Confidential", size=8.5, color=C_GREY)

    if os.path.exists(_LOGO):
        doc.add_picture(_LOGO, width=Inches(0.8))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path


# ── Markdown (Docusaurus) ─────────────────────────────────────────────────────
def _screen_block(fit: DealFit, deal: DealInput) -> str:
    tier = TIER_LABEL.get(fit.quality_tier, fit.quality_tier)
    gate_text = f"clears gate ({tier})" if fit.gate else "below gate threshold"
    head = f"## Screen — {date.today().isoformat()}"
    if deal.round:
        head += f" · {deal.round}"
    lines = [
        head,
        "",
        f"**Fit score: {fit.fit_score:.1f} / 4.0 — {gate_text}**",
        "",
        "| Dimension | Score | Evidence |",
        "| --- | --- | --- |",
    ]
    for param in fit.params:
        ev = param.evidence.replace("|", "/").replace("\n", " ")
        lines.append(f"| {PARAM_LABELS.get(param.key, param.key)} | {param.score:.0f} / 4 | {ev} |")
    lines += ["", "**Rationale**", "", fit.rationale, "",
              f"*Confidence: {fit.confidence}*", "", "---", ""]
    return "\n".join(lines)


def _new_page(fit: DealFit, deal: DealInput, slug: str, docx_href: str) -> str:
    domain = normalize_domain(deal.domain)
    header = [
        "---",
        f"title: {deal.name}",
        f"description: Deal screens for {deal.name}",
        f"company_id: {company_id(deal)}",
    ]
    if domain:
        header.append(f"website: {domain}")
    header += ["---", "", f"# {deal.name}", ""]

    meta = []
    if domain:
        meta.append(f"[{domain}](https://{domain})")
    meta.append(f"[Download latest screen (Word) →]({docx_href})")
    header += [" · ".join(meta), "", _SCREENS_START, "", _screen_block(fit, deal), _SCREENS_END, ""]
    return "\n".join(header)


def write_company_screen(fit: DealFit, deal: DealInput, hub_root: str, docx_root: str) -> dict:
    """Write/append one screen for a company. Prepends to the dated history if the
    company page already exists; creates it otherwise. The .docx always reflects
    the latest screen. Returns slug + output paths + whether it was an update."""
    slug = company_id(deal)
    docx_path = os.path.join(docx_root, f"{slug}.docx")
    md_path = os.path.join(hub_root, f"{slug}.md")
    docx_href = f"/research/companies/{slug}.docx"

    build_docx(fit, deal, docx_path)

    updated = os.path.exists(md_path)
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    if updated:
        with open(md_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if _SCREENS_START in existing:
            block = "\n" + _screen_block(fit, deal)
            content = existing.replace(_SCREENS_START, _SCREENS_START + block, 1)
        else:  # legacy/hand-edited page without markers — fall back to a fresh page
            content = _new_page(fit, deal, slug, docx_href)
    else:
        content = _new_page(fit, deal, slug, docx_href)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"slug": slug, "docx": docx_path, "markdown": md_path, "updated": updated}
