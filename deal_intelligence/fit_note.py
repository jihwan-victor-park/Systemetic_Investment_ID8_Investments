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
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from . import rubric, config
from .schemas import DealFit, DealInput

C_CHARCOAL = RGBColor(0x1A, 0x1A, 0x1A)
C_GREY = RGBColor(0x82, 0x82, 0x82)
C_SOFT = RGBColor(0x3C, 0x3C, 0x3C)
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
C_ROW_ALT = RGBColor(0xF5, 0xF5, 0xF5)
HAIR_HEX = "E4DFD5"
DARK_HEX = "1A1A1A"
ALT_HEX = "F5F5F5"
FONT_HEAD = "Roboto Serif"
FONT_BODY = "Sora"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGO = os.path.join(_REPO_ROOT, "design", "assets", "id8_charcoal.png")

PARAM_LABELS = {p["key"]: p["label"] for p in rubric.PARAMS}
TIER_LABEL = {"strong_go": "Strong Go", "go_ic": "Go / IC Review",
              "more_diligence": "More Diligence", "pass": "Pass", "watch_list": "Watch List",
              "error": "Scoring Failed"}


def _badge_text(fit: DealFit) -> str:
    """Short status text for the fit-score badge, in title case -- callers
    apply .upper() (docx) or .lower() (markdown/email prose) as needed.
    hard_auto_pass and watch_list are reported by the model, not derived from
    fit_score, and take precedence over the threshold bands (see stage1_fit.py).
    quality_tier == "error" means scoring itself broke (see stage1_fit.run) --
    checked first so a broken run is never rendered as a real Pass."""
    if fit.quality_tier == "error":
        return "Scoring Failed — Not Screened"
    if fit.hard_auto_pass:
        return "Pass — Hard Auto-Pass"
    if fit.quality_tier == "watch_list":
        return "Watch List — Outside Mandate (Stage)"
    tier = TIER_LABEL.get(fit.quality_tier, fit.quality_tier)
    if fit.gate:
        return f"Clears Gate · {tier}"
    if fit.quality_tier == "more_diligence":
        return "More Diligence"
    return "Pass"

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


def hub_url(deal: DealInput, base: str = None) -> str:
    """The deployed-hub research page for this company. Predictable from the slug,
    so it can be written onto the Attio deal even before the page is published."""
    base = (base or config.HUB_BASE_URL).rstrip("/")
    return f"{base}/docs/research/companies/{company_id(deal)}"


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


def _cell_borders(cell, color=HAIR_HEX, size=4, sides=("bottom",)):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "right", "bottom"):
        el = OxmlElement(f"w:{side}")
        if side in sides:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(size))
            el.set(qn("w:color"), color)
        else:
            el.set(qn("w:val"), "nil")
        borders.append(el)
    tcPr.append(borders)


def _cell_shading(cell, fill_hex: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tcPr.append(shd)


def _cell_padding(cell, top=40, bottom=40, left=60, right=60):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def _hairline_under(paragraph, color=DARK_HEX, size=6):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:color"), color)
    bottom.set(qn("w:space"), "4")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_page_number(paragraph):
    """Insert 'Page N of M' into an existing paragraph."""
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(paragraph, "Page ", size=8.5, color=C_GREY)
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "begin")
    paragraph._p.append(fld)
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    paragraph._p.append(instr)
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    paragraph._p.append(fld2)
    _run(paragraph, " of ", size=8.5, color=C_GREY)
    fld3 = OxmlElement("w:fldChar")
    fld3.set(qn("w:fldCharType"), "begin")
    paragraph._p.append(fld3)
    instr2 = OxmlElement("w:instrText")
    instr2.set(qn("xml:space"), "preserve")
    instr2.text = " NUMPAGES "
    paragraph._p.append(instr2)
    fld4 = OxmlElement("w:fldChar")
    fld4.set(qn("w:fldCharType"), "end")
    paragraph._p.append(fld4)


def build_docx(fit: DealFit, deal: DealInput, output_path: str):
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(1.0)
    section.left_margin = section.right_margin = Inches(1.0)

    normal = doc.styles["Normal"]
    normal.font.name = FONT_BODY
    normal.font.size = Pt(10.5)

    # ── Page number in footer ──
    footer_p = section.footer.paragraphs[0]
    _add_page_number(footer_p)

    # ── Header: logo left, label right ──
    header = section.header
    hdr_table = header.add_table(rows=1, cols=2, width=Inches(6.5))
    hdr_table.autofit = False
    hdr_table.columns[0].width = Inches(1.0)
    hdr_table.columns[1].width = Inches(5.5)
    logo_cell, label_cell = hdr_table.rows[0].cells
    if os.path.exists(_LOGO):
        logo_cell.paragraphs[0].add_run().add_picture(_LOGO, width=Inches(0.65))
    label_p = label_cell.paragraphs[0]
    label_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run(label_p, "DEAL SCREEN  ·  ID8 INVESTMENTS  ·  CONFIDENTIAL",
         size=8.0, color=C_GREY, all_caps=True)
    label_p.paragraph_format.space_before = Pt(4)
    for cell in (logo_cell, label_cell):
        _cell_borders(cell, sides=("bottom",), color=DARK_HEX, size=4)

    # ── Company title ──
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(4)
    title_p.paragraph_format.space_after = Pt(2)
    _run(title_p, deal.name, font=FONT_HEAD, size=22, bold=True)

    # ── Sub-line: domain · round · HQ · lead investors ──
    domain = normalize_domain(deal.domain)
    sub_parts = _context_bits(deal)
    if domain:
        sub_parts = [domain] + sub_parts
    if sub_parts:
        sub_p = doc.add_paragraph()
        sub_p.paragraph_format.space_after = Pt(2)
        _run(sub_p, "   ·   ".join(sub_parts), size=10.5, color=C_GREY)

    # ── Screened date label ──
    date_p = doc.add_paragraph()
    date_p.paragraph_format.space_after = Pt(10)
    _run(date_p, f"Screened {date.today().isoformat()}",
         size=9.0, color=C_GREY)

    # ── Section heading: FIT ASSESSMENT ──
    sec_p = doc.add_paragraph()
    sec_p.paragraph_format.space_after = Pt(6)
    _run(sec_p, "FIT ASSESSMENT", font=FONT_HEAD, size=14, bold=True)
    _hairline_under(sec_p)

    # ── Score + gate badge ──
    score_p = doc.add_paragraph()
    score_p.paragraph_format.space_before = Pt(6)
    score_p.paragraph_format.space_after = Pt(2) if (fit.hard_auto_pass and fit.hard_auto_pass_reason) else Pt(12)
    _run(score_p, f"{fit.fit_score:.1f} / 4.0", font=FONT_HEAD, size=16, bold=True)
    _run(score_p, f"   (raw {fit.raw_score:.1f})", size=10.5, color=C_GREY)
    _run(score_p, f"   —   {_badge_text(fit).upper()}", size=10.5, color=C_GREY)

    if fit.hard_auto_pass and fit.hard_auto_pass_reason:
        reason_p = doc.add_paragraph()
        reason_p.paragraph_format.space_after = Pt(12)
        _run(reason_p, f"Hard auto-pass: {fit.hard_auto_pass_reason}", size=9.5, color=C_SOFT)

    # ── Rubric table: dark header, alternating rows ──
    col_widths = [Inches(1.85), Inches(0.55), Inches(4.1)]
    table = doc.add_table(rows=1, cols=3)
    table.autofit = False

    # Header row
    hrow = table.rows[0].cells
    for i, (label, w) in enumerate(zip(["Dimension", "Score", "Evidence"], col_widths)):
        hrow[i].width = w
        _cell_shading(hrow[i], DARK_HEX)
        _cell_padding(hrow[i])
        p = hrow[i].paragraphs[0]
        _run(p, label, size=9.0, bold=True, color=C_WHITE, all_caps=True)

    # Data rows
    for idx, param in enumerate(fit.params):
        row = table.add_row().cells
        fill = ALT_HEX if idx % 2 == 0 else "FFFFFF"
        for i, (c, w) in enumerate(zip(row, col_widths)):
            c.width = w
            _cell_shading(c, fill)
            _cell_padding(c)
            _cell_borders(c, color=HAIR_HEX, size=4, sides=("bottom",))
        _run(row[0].paragraphs[0], PARAM_LABELS.get(param.key, param.key), size=9.5)
        score_run = row[1].paragraphs[0]
        _run(score_run, f"{param.score:.0f}", size=9.5, bold=True)
        _run(score_run, " / 4", size=8.5, color=C_GREY)
        _md_runs(row[2].paragraphs[0], param.evidence, size=9.0, color=C_SOFT)

    # ── Section heading: RATIONALE ──
    doc.add_paragraph().paragraph_format.space_after = Pt(8)
    rat_sec = doc.add_paragraph()
    rat_sec.paragraph_format.space_after = Pt(6)
    _run(rat_sec, "RATIONALE", font=FONT_HEAD, size=12, bold=True)
    _hairline_under(rat_sec)

    rat_p = doc.add_paragraph()
    rat_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    rat_p.paragraph_format.space_before = Pt(6)
    rat_p.paragraph_format.space_after = Pt(6)
    _md_runs(rat_p, fit.rationale, size=10.5)

    # ── Confidence + footer note ──
    conf_p = doc.add_paragraph()
    conf_p.paragraph_format.space_before = Pt(4)
    _run(conf_p, f"Confidence: {fit.confidence}", size=9.0, color=C_GREY)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path


def build_docx_bytes(fit: DealFit, deal: DealInput) -> bytes:
    """Same as build_docx but returns the .docx as bytes (no disk write).
    Used by hub_push when running on Cloud Run."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name
    build_docx(fit, deal, tmp_path)
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data


# ── Markdown (Docusaurus) ─────────────────────────────────────────────────────
def _linkify_md(text: str, citations: list) -> str:
    """Turn Perplexity's [1][2] source markers into markdown links to the cited
    URLs. Markers with no matching citation are dropped rather than left dangling."""
    citations = citations or []

    def repl(m):
        n = int(m.group(1))
        if 1 <= n <= len(citations):
            return f"[[{n}]]({citations[n - 1]})"
        return ""

    return re.sub(r"\[(\d+)\]", repl, str(text or ""))


def _screen_block(fit: DealFit, deal: DealInput) -> str:
    cites = fit.citations
    lines = [
        _screen_heading(deal),
        "",
        f"**Fit score: {fit.fit_score:.1f} / 4.0** (raw {fit.raw_score:.1f}) — {_badge_text(fit).lower()}",
        "",
    ]
    if fit.hard_auto_pass and fit.hard_auto_pass_reason:
        lines += [f"*Hard auto-pass: {_linkify_md(fit.hard_auto_pass_reason, cites)}*", ""]
    lines += [
        "| Dimension | Score | Evidence |",
        "| --- | --- | --- |",
    ]
    for param in fit.params:
        ev = _linkify_md(param.evidence.replace("|", "/").replace("\n", " "), cites)
        lines.append(f"| {PARAM_LABELS.get(param.key, param.key)} | {param.score:.0f} / 4 | {ev} |")
    lines += ["", "**Rationale**", "", _linkify_md(fit.rationale, cites), "",
              f"*Confidence: {fit.confidence}*", ""]
    if cites:
        lines += ["**Sources**", ""]
        # Markdown link syntax — MDX rejects bare <url> autolinks.
        lines += [f"{i}. [{url}]({url})" for i, url in enumerate(cites, 1)]
        lines += [""]
    lines += ["---", ""]
    return "\n".join(lines)


def _screen_heading(deal: DealInput) -> str:
    head = f"## Screen — {date.today().isoformat()}"
    if deal.round:
        head += f" · {deal.round}"
    return head


def _upsert_screen(existing: str, fit: DealFit, deal: DealInput) -> str:
    """Insert the new screen at the top of the history, replacing any existing
    screen with the same heading (same day + round) so a same-day re-run refreshes
    rather than duplicates. A later round keeps its own dated entry."""
    pre, rest = existing.split(_SCREENS_START, 1)
    mid, post = rest.split(_SCREENS_END, 1)
    new_heading = _screen_heading(deal)
    # split the history into individual screen blocks
    blocks = re.split(r"(?=^## Screen )", mid, flags=re.MULTILINE)
    kept = [b for b in blocks if b.strip() and not b.startswith(new_heading)]
    body = "\n" + _screen_block(fit, deal) + "".join(kept)
    return pre + _SCREENS_START + body + _SCREENS_END + post


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


def _build_screen_content(fit: DealFit, deal: DealInput, slug: str, docx_path: str) -> str:
    """Return the markdown string for a company screen without touching disk.
    Used by the GitHub API push path (Cloud Run)."""
    docx_href = f"/research/companies/{slug}.docx"
    existing_content = None
    # On Cloud Run there is no local file; caller supplies None implicitly.
    if existing_content is not None and _SCREENS_START in existing_content:
        return _upsert_screen(existing_content, fit, deal)
    return _new_page(fit, deal, slug, docx_href)


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
        if _SCREENS_START in existing and _SCREENS_END in existing:
            content = _upsert_screen(existing, fit, deal)
        else:  # legacy/hand-edited page without markers — fall back to a fresh page
            content = _new_page(fit, deal, slug, docx_href)
    else:
        content = _new_page(fit, deal, slug, docx_href)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"slug": slug, "docx": docx_path, "markdown": md_path, "updated": updated}
