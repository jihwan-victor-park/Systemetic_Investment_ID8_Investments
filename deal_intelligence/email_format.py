"""Render Stage 1 fit results into an email-ready HTML block.

n8n calls /screen-deals, polls /screen-deals/status, and drops the returned
`email_html` straight into a Gmail node — so the screening rating + rationale
ride along in the same deal-intake email the team already scans. All styling is
inline (email clients strip <style> blocks); ID8 "Latent Order" palette.
"""
import re
from datetime import date

from . import rubric
from .schemas import DealFit

PARAM_LABELS = {p["key"]: p["label"] for p in rubric.PARAMS}
TIER_LABEL = {"strong_go": "Strong Go", "go_ic": "Go / IC Review",
              "more_diligence": "More Diligence", "pass": "Pass", "watch_list": "Watch List",
              "error": "Scoring Failed"}

CHARCOAL = "#1A1A1A"
GREY = "#828282"
SOFT = "#3C3C3C"
HAIR = "#E4DFD5"
PASS_BG = "#EAF3DE"
MORE_DILIGENCE_BG = "#FBF0D9"
WATCH_LIST_BG = "#E8EEF5"
FAIL_BG = "#F5F5F5"
ERROR_BG = "#F5DCDC"
BODY_FONT = "'Sora', 'Helvetica Neue', Arial, sans-serif"


def _esc(text) -> str:
    """HTML-escape, then convert Perplexity's markdown **bold** to <strong>."""
    s = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def _badge(fit: DealFit) -> tuple:
    """(background color, badge text). hard_auto_pass and watch_list are
    reported by the model, not derived from fit_score, and take precedence
    over the threshold bands (see stage1_fit.py). quality_tier == "error"
    means scoring itself broke (see stage1_fit.run) -- checked first so a
    broken run is never rendered as a real Pass."""
    if fit.quality_tier == "error":
        return ERROR_BG, "SCORING FAILED — NOT SCREENED"
    if fit.hard_auto_pass:
        return FAIL_BG, "HARD AUTO-PASS"
    if fit.quality_tier == "watch_list":
        return WATCH_LIST_BG, "WATCH LIST"
    tier = TIER_LABEL.get(fit.quality_tier, fit.quality_tier)
    if fit.gate:
        return PASS_BG, f"CLEARS GATE · {tier.upper()}"
    if fit.quality_tier == "more_diligence":
        return MORE_DILIGENCE_BG, "MORE DILIGENCE"
    return FAIL_BG, "PASS"


def _deal_card(fit: DealFit, hub_url: str = None) -> str:
    badge_bg, badge_txt = _badge(fit)
    hard_pass_line = (
        f'<div style="margin:2px 0 8px 0;font-size:12px;color:{SOFT};">'
        f'<span style="font-weight:600;">Hard auto-pass.</span> {_esc(fit.hard_auto_pass_reason)}</div>'
        if fit.hard_auto_pass and fit.hard_auto_pass_reason else ''
    )

    rows = ""
    for p in fit.params:
        rows += (
            f'<tr>'
            f'<td style="padding:5px 10px 5px 0;border-bottom:1px solid {HAIR};'
            f'font-size:13px;color:{CHARCOAL};white-space:nowrap;vertical-align:top;">{_esc(PARAM_LABELS.get(p.key, p.key))}</td>'
            f'<td style="padding:5px 10px;border-bottom:1px solid {HAIR};'
            f'font-size:13px;color:{CHARCOAL};font-weight:600;vertical-align:top;">{p.score:.1f}<span style="color:{GREY};font-weight:400;"> / 4</span></td>'
            f'<td style="padding:5px 0 5px 0;border-bottom:1px solid {HAIR};'
            f'font-size:12px;color:{SOFT};line-height:1.4;">{_esc(p.evidence)}</td>'
            f'</tr>'
        )

    return (
        f'<div style="margin:0 0 26px 0;font-family:{BODY_FONT};">'
        f'<div style="font-size:17px;font-weight:700;color:{CHARCOAL};">{_esc(fit.name)}</div>'
        f'<div style="margin:6px 0 10px 0;">'
        f'<span style="font-size:15px;font-weight:700;color:{CHARCOAL};">Fit score {fit.fit_score:.1f} / 4.0</span>'
        f'<span style="font-size:12px;font-weight:400;color:{GREY};margin-left:6px;">(raw {fit.raw_score:.1f})</span>'
        f'<span style="display:inline-block;margin-left:10px;padding:2px 8px;background:{badge_bg};'
        f'border-radius:3px;font-size:11px;letter-spacing:0.5px;color:{CHARCOAL};">{_esc(badge_txt)}</span>'
        f'</div>'
        f'{hard_pass_line}'
        f'<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;margin:0 0 10px 0;">'
        f'<tr>'
        f'<th align="left" style="padding:0 10px 4px 0;border-bottom:2px solid {CHARCOAL};font-size:10px;letter-spacing:1px;color:{CHARCOAL};text-transform:uppercase;">Dimension</th>'
        f'<th align="left" style="padding:0 10px 4px 10px;border-bottom:2px solid {CHARCOAL};font-size:10px;letter-spacing:1px;color:{CHARCOAL};text-transform:uppercase;">Score</th>'
        f'<th align="left" style="padding:0 0 4px 0;border-bottom:2px solid {CHARCOAL};font-size:10px;letter-spacing:1px;color:{CHARCOAL};text-transform:uppercase;">Evidence</th>'
        f'</tr>{rows}</table>'
        f'<div style="font-size:13px;color:{CHARCOAL};line-height:1.5;">'
        f'<span style="font-weight:600;">Rationale.</span> {_esc(fit.rationale)}</div>'
        f'<div style="margin-top:6px;font-size:11px;color:{GREY};">'
        f'Confidence: {_esc(fit.confidence)}'
        + (f' · <a href="{_esc(hub_url)}" style="color:{CHARCOAL};">Full research →</a>' if hub_url else '')
        + f'</div>'
        f'</div>'
    )


def email_html(fits: list, title: str = "Deal Intelligence — Stage 1 Screen", hub_urls: dict = None) -> str:
    """Full HTML block for the body of the deal-intake email. `fits` sorted by
    score, highest first; gated deals are flagged, borderline deals flagged amber.
    hub_urls: optional {record_id: url} to render a 'Full research →' link per deal."""
    hub_urls = hub_urls or {}
    fits = sorted(fits, key=lambda f: f.fit_score, reverse=True)
    gated = sum(1 for f in fits if f.gate)
    more_diligence = sum(1 for f in fits if f.quality_tier == "more_diligence")
    watch_list = sum(1 for f in fits if f.quality_tier == "watch_list")
    cards = "".join(_deal_card(f, hub_urls.get(f.record_id)) for f in fits)
    summary = f"{len(fits)} screened · {gated} cleared the gate"
    if more_diligence:
        summary += f" · {more_diligence} more diligence"
    if watch_list:
        summary += f" · {watch_list} watch list"
    return (
        f'<div style="font-family:{BODY_FONT};max-width:680px;color:{CHARCOAL};">'
        f'<div style="font-size:20px;font-weight:700;border-bottom:2px solid {CHARCOAL};padding-bottom:6px;margin-bottom:4px;">{_esc(title)}</div>'
        f'<div style="font-size:12px;color:{GREY};margin-bottom:18px;">'
        f'{summary} · {date.today().isoformat()}</div>'
        f'{cards}'
        f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid {HAIR};font-size:11px;color:{GREY};">'
        f'ID8 Investments · Confidential · Scored against the ID8 fit rubric (1–4 per dimension).</div>'
        f'</div>'
    )


def email_text(fits: list) -> str:
    """Plain-text fallback for the multipart email."""
    fits = sorted(fits, key=lambda f: f.fit_score, reverse=True)
    out = []
    for f in fits:
        _, badge_txt = _badge(f)
        out.append(f"{f.name} — fit {f.fit_score:.1f}/4.0 (raw {f.raw_score:.1f}) [{badge_txt}]")
        if f.hard_auto_pass and f.hard_auto_pass_reason:
            out.append(f"  Hard auto-pass: {f.hard_auto_pass_reason}")
        for p in f.params:
            out.append(f"  - {PARAM_LABELS.get(p.key, p.key)}: {p.score:.1f}/4")
        out.append(f"  Rationale: {f.rationale}")
        out.append("")
    return "\n".join(out)
