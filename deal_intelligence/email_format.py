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


# ── Intake email (the /process, /process-watchlist, /process-top10 digest) ────
# Added 2026-08-03. Previously each intake workflow built its own email HTML in
# its own n8n Code node, and they had drifted badly: only the PitchBook weekly
# node rendered the Stage 1 fit block at all, so the Top 10 VC and Watchlist
# emails showed no score even when screening had run and paid for it. And since
# run_pipeline only ever returned newly-created deals, a company the OTHER
# intake source had already landed appeared in no email at all.
#
# Rendering here instead means one implementation for every flow: n8n's Gmail
# node just uses {{ $json.email_html }} and the per-flow JS goes away.

_TOP10_BG = "#EDE7F5"


def _fact_cell(label: str, value: str, width: str = "33%", pad_right: str = "12px") -> str:
    return (
        f'<td style="width:{width};padding-right:{pad_right};vertical-align:top;">'
        f'<div style="font-size:10px;font-weight:600;letter-spacing:1px;'
        f'text-transform:uppercase;color:{GREY};margin-bottom:2px;">{_esc(label)}</div>'
        f'<div style="font-size:14px;color:{CHARCOAL};">{_esc(value) or "—"}</div>'
        f'</td>'
    )


def _placement_badge(deal: dict) -> str:
    """Where this deal landed. `hub_tags` carrying both radar and qualified is
    the Series B dual case (see pipeline/app.py's determine_placement) -- worth
    showing explicitly, since Attio can only display one of the two."""
    tags = deal.get("hub_tags") or []
    stage = deal.get("stage") or ""
    if "radar" in tags and "qualified" in tags:
        text = "Qualified + Radar"
    elif stage:
        text = stage
    else:
        return ""
    return (
        f'<span style="display:inline-block;margin-left:8px;padding:2px 8px;'
        f'background:{WATCH_LIST_BG};border-radius:3px;font-size:10px;'
        f'letter-spacing:0.5px;text-transform:uppercase;color:{CHARCOAL};">{_esc(text)}</span>'
    )


def _top10_badge(deal: dict) -> str:
    """Which Top 10 firms are actually on the cap table, resolved by
    deal_intelligence.tier1_firms from investor domains + names."""
    firms = deal.get("top10_firms") or []
    if not firms:
        return ""
    return (
        f'<div style="margin:6px 0 0 0;font-size:11px;color:{SOFT};">'
        f'<span style="display:inline-block;padding:2px 8px;background:{_TOP10_BG};'
        f'border-radius:3px;font-size:10px;letter-spacing:0.5px;'
        f'text-transform:uppercase;color:{CHARCOAL};">Top 10 VC</span>'
        f'&nbsp; {_esc(", ".join(firms))}</div>'
    )


def _fit_block(deal: dict) -> str:
    """The Stage 1 result for a deal screened on THIS run. Mirrors _deal_card's
    dimension table, driven off the flat dict run_pipeline builds rather than a
    DealFit object."""
    if deal.get("fit_score") is None:
        return ""
    tier = deal.get("fit_tier") or "pass"
    if deal.get("fit_hard_auto_pass"):
        badge_bg, badge_txt = FAIL_BG, "HARD AUTO-PASS"
    elif tier == "error":
        badge_bg, badge_txt = ERROR_BG, "SCORING FAILED — NOT SCREENED"
    elif tier == "watch_list":
        badge_bg, badge_txt = WATCH_LIST_BG, "WATCH LIST"
    elif deal.get("fit_gate"):
        badge_bg, badge_txt = PASS_BG, f"CLEARS GATE · {TIER_LABEL.get(tier, tier).upper()}"
    elif tier == "more_diligence":
        badge_bg, badge_txt = MORE_DILIGENCE_BG, "MORE DILIGENCE"
    else:
        badge_bg, badge_txt = FAIL_BG, "PASS"

    rows = ""
    for p in deal.get("fit_params") or []:
        rows += (
            f'<tr>'
            f'<td style="padding:5px 10px 5px 0;border-bottom:1px solid {HAIR};'
            f'font-size:13px;color:{CHARCOAL};white-space:nowrap;vertical-align:top;">'
            f'{_esc(PARAM_LABELS.get(p.get("key"), p.get("key")))}</td>'
            f'<td style="padding:5px 10px;border-bottom:1px solid {HAIR};font-size:13px;'
            f'color:{CHARCOAL};font-weight:600;vertical-align:top;">{p.get("score", 0):.1f}'
            f'<span style="color:{GREY};font-weight:400;"> / 4</span></td>'
            f'<td style="padding:5px 0;border-bottom:1px solid {HAIR};font-size:12px;'
            f'color:{SOFT};line-height:1.4;">{_esc(p.get("evidence", ""))}</td>'
            f'</tr>'
        )

    hard = ""
    if deal.get("fit_hard_auto_pass") and deal.get("fit_hard_auto_pass_reason"):
        hard = (f'<div style="margin:2px 0 8px 0;font-size:12px;color:{SOFT};">'
                f'<span style="font-weight:600;">Hard auto-pass.</span> '
                f'{_esc(deal["fit_hard_auto_pass_reason"])}</div>')

    hub = ""
    if deal.get("hub_url"):
        hub = (f' · <a href="{_esc(deal["hub_url"])}" style="color:{CHARCOAL};">'
               f'Full research →</a>')

    return (
        f'<div style="margin-top:14px;padding-top:12px;border-top:1px solid {HAIR};">'
        f'<div style="margin-bottom:8px;">'
        f'<span style="font-size:10px;font-weight:600;letter-spacing:1px;'
        f'text-transform:uppercase;color:{GREY};">Deal Screen</span>'
        f'<span style="font-size:15px;font-weight:700;color:{CHARCOAL};margin-left:8px;">'
        f'{deal["fit_score"]:.1f}<span style="font-size:12px;color:{GREY};font-weight:400;"> / 4.0</span></span>'
        f'<span style="display:inline-block;margin-left:10px;padding:2px 8px;'
        f'background:{badge_bg};border-radius:3px;font-size:10px;letter-spacing:0.5px;'
        f'color:{CHARCOAL};">{_esc(badge_txt)}</span>'
        f'</div>'
        f'{hard}'
        f'<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;'
        f'margin:0 0 10px 0;">{rows}</table>'
        f'<div style="font-size:13px;color:{CHARCOAL};line-height:1.5;">'
        f'<span style="font-weight:600;">Rationale.</span> {_esc(deal.get("fit_rationale", ""))}</div>'
        f'<div style="margin-top:6px;font-size:11px;color:{GREY};">'
        f'Confidence: {_esc(deal.get("fit_confidence") or "—")}{hub}</div>'
        f'</div>'
    )


def _prior_screen_line(deal: dict) -> str:
    """For a re-seen deal: its EXISTING screen, not a fresh one. Reporting the
    prior score is the whole point of surfacing these -- it's what tells you
    whether the deal was already assessed and how it scored, without paying to
    re-research it."""
    prior = deal.get("prior_screen") or {}
    if not prior:
        return ""
    score = prior.get("fitScore")
    bits = []
    if score is not None:
        bits.append(f'<span style="font-weight:700;color:{CHARCOAL};">{score:.1f} / 4.0</span>')
    if prior.get("gate"):
        bits.append(f'<span style="color:{CHARCOAL};">clears gate</span>')
    if prior.get("date"):
        bits.append(f'screened {_esc(prior["date"])}')
    link = (f' · <a href="{_esc(deal["hub_url"])}" style="color:{CHARCOAL};">Full research →</a>'
            if deal.get("hub_url") else '')
    return (f'<div style="margin-top:6px;font-size:12px;color:{SOFT};">'
            f'Already screened: {" · ".join(bits) or "on file"}{link}</div>')


def _intake_card(deal: dict, screened_now: bool) -> str:
    name = _esc(deal.get("company", ""))
    if deal.get("record_id"):
        name = (f'<a href="https://app.attio.com/i-d-8-investments/deals/record/'
                f'{_esc(deal["record_id"])}/overview" style="color:{CHARCOAL};'
                f'text-decoration:none;">{name} ↗</a>')
    site = ""
    if deal.get("website"):
        site = (f'<div style="margin:2px 0 8px 0;font-size:12px;">'
                f'<a href="https://{_esc(deal["website"])}" style="color:{CHARCOAL};">'
                f'{_esc(deal["website"])}</a></div>')

    return (
        f'<div style="margin:0 0 26px 0;">'
        f'<div style="font-size:17px;font-weight:700;color:{CHARCOAL};">{name}'
        f'<span style="font-size:12px;font-weight:400;color:{GREY};margin-left:8px;">'
        f'{_esc(deal.get("series", ""))}</span>{_placement_badge(deal)}</div>'
        f'{site}'
        f'{_top10_badge(deal)}'
        + (f'<div style="margin:8px 0;font-size:13px;color:{SOFT};line-height:1.5;">'
           f'{_esc(deal.get("description", ""))}</div>' if deal.get("description") else '')
        + f'<table cellpadding="0" cellspacing="0" style="width:100%;margin:8px 0;">'
          f'<tr>'
          + _fact_cell("Deal Size", deal.get("deal_size", ""))
          + _fact_cell("Post Valuation", deal.get("post_valuation", ""))
          + _fact_cell("Date", deal.get("deal_date", ""), pad_right="0")
          + f'</tr><tr>'
          + _fact_cell("Location", deal.get("hq_location", ""))
          + _fact_cell("Lead Investors", deal.get("lead_investors", ""))
          + _fact_cell("New Investors", deal.get("new_investors", ""), pad_right="0")
          + f'</tr></table>'
        + (_fit_block(deal) if screened_now else _prior_screen_line(deal))
        + f'</div>'
    )


def intake_email_html(deals: list, title: str, hub_base_url: str = None) -> str:
    """The full intake digest for one workflow run.

    deals: run_pipeline's `deals` rows, enriched by _run_pipeline_bg with the
    fit_* fields for anything screened on this run. Each row carries `is_new`
    (brand new to Attio vs already present via another source) and
    `already_screened`.

    Splits into two sections deliberately: new deals with their full Stage 1
    screen, then an "already in Attio" section reporting each re-seen deal's
    EXISTING score. Both are needed -- the second section is what makes the
    cross-source overlap visible instead of silently dropped."""
    new = [d for d in deals if d.get("is_new")]
    reseen = [d for d in deals if not d.get("is_new")]
    # Highest score first within each section; unscored last.
    new.sort(key=lambda d: (d.get("fit_score") is None, -(d.get("fit_score") or 0)))
    reseen.sort(key=lambda d: ((d.get("prior_screen") or {}).get("fitScore") is None,
                               -((d.get("prior_screen") or {}).get("fitScore") or 0)))

    screened = sum(1 for d in new if d.get("fit_score") is not None)
    gated = sum(1 for d in deals if d.get("fit_gate")
                or (d.get("prior_screen") or {}).get("gate"))
    top10 = sum(1 for d in deals if d.get("top10_firms"))

    summary = f"{len(new)} new"
    if reseen:
        summary += f" · {len(reseen)} already in Attio"
    if screened:
        summary += f" · {screened} screened"
    if gated:
        summary += f" · {gated} clear the gate"
    if top10:
        summary += f" · {top10} Top 10 VC-backed"

    body = ""
    if new:
        body += "".join(_intake_card(d, screened_now=True) for d in new)
    if reseen:
        body += (
            f'<div style="margin:8px 0 18px 0;padding-top:10px;'
            f'border-top:2px solid {CHARCOAL};font-size:11px;font-weight:600;'
            f'letter-spacing:1px;text-transform:uppercase;color:{CHARCOAL};">'
            f'Already in Attio — updated, not re-screened</div>'
            f'<div style="font-size:12px;color:{GREY};margin-bottom:16px;">'
            f'These arrived in this export but were already on file from another '
            f'source. Investor links, the Top 10 VC flag and hub tags were '
            f'refreshed; their existing screen is reported below rather than '
            f'paying to research them again.</div>'
        )
        body += "".join(_intake_card(d, screened_now=False) for d in reseen)
    if not deals:
        body = (f'<div style="font-size:13px;color:{GREY};">'
                f'No deals in this export.</div>')

    return (
        f'<div style="font-family:{BODY_FONT};max-width:680px;color:{CHARCOAL};">'
        f'<div style="font-size:20px;font-weight:700;border-bottom:2px solid {CHARCOAL};'
        f'padding-bottom:6px;margin-bottom:4px;">{_esc(title)}</div>'
        f'<div style="font-size:12px;color:{GREY};margin-bottom:18px;">'
        f'{summary} · {date.today().isoformat()}</div>'
        f'{body}'
        f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid {HAIR};'
        f'font-size:11px;color:{GREY};">ID8 Investments · Confidential · '
        f'Scored against the ID8 fit rubric (1–4 per dimension).</div>'
        f'</div>'
    )


def intake_email_text(deals: list, title: str) -> str:
    """Plain-text fallback for the intake digest."""
    out = [title, ""]
    for label, rows, is_new in (("NEW", [d for d in deals if d.get("is_new")], True),
                                 ("ALREADY IN ATTIO", [d for d in deals if not d.get("is_new")], False)):
        if not rows:
            continue
        out.append(f"— {label} —")
        for d in rows:
            line = f"{d.get('company','')} ({d.get('series','')})"
            if is_new and d.get("fit_score") is not None:
                line += f" — fit {d['fit_score']:.1f}/4.0"
                if d.get("fit_gate"):
                    line += " [CLEARS GATE]"
            elif not is_new:
                prior = d.get("prior_screen") or {}
                if prior.get("fitScore") is not None:
                    line += f" — already screened {prior['fitScore']:.1f}/4.0 ({prior.get('date','')})"
                else:
                    line += " — already in Attio"
            if d.get("top10_firms"):
                line += f" [Top 10: {', '.join(d['top10_firms'])}]"
            out.append("  " + line)
        out.append("")
    return "\n".join(out)


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
