"""Covers the intake digest renderer (email_format.intake_email_html/_text).

Why this exists: each intake workflow used to assemble its own email HTML in its
own n8n Code node, and they had drifted -- only the PitchBook weekly node
rendered the Stage 1 fit block, so the Top 10 VC and Watchlist emails showed no
score even when screening had already run and been paid for. And because
run_pipeline only returned newly-created deals, a company already on file from
the other intake source appeared in no email at all. These pin the replacement.
"""
import re

import pytest

from deal_intelligence import email_format as ef


def _new_deal(**over):
    d = {
        "company": "Acme AI", "series": "Series B", "website": "acme.com",
        "is_new": True, "record_id": "rec_1",
        "deal_size": "$40M", "post_valuation": "$400M", "deal_date": "2026-07-15",
        "hq_location": "San Francisco, CA", "lead_investors": "Sequoia Capital",
        "new_investors": "Index Ventures", "description": "AI agents for logistics.",
        "stage": "Qualified", "hub_tags": ["radar", "qualified"],
        "top10_firms": ["Sequoia Capital", "Index Ventures"],
        "fit_score": 3.4, "fit_raw_score": 3.2, "fit_gate": True, "fit_tier": "go_ic",
        "fit_rationale": "Strong team, real revenue.", "fit_confidence": "high",
        "fit_params": [{"key": "ai_score", "score": 4.0, "evidence": "Core AI product."}],
        "hub_url": "https://hub.example.com/docs/qualified-deals/acme",
    }
    d.update(over)
    return d


def _reseen_deal(**over):
    d = {
        "company": "Beta Corp", "series": "Series D", "website": "beta.com",
        "is_new": False, "record_id": "rec_2",
        "deal_size": "$120M", "post_valuation": "$1.2B", "deal_date": "2026-06-01",
        "hq_location": "New York, NY", "lead_investors": "Bain & Company",
        "new_investors": "", "description": "Fintech infra.",
        "stage": "Qualified", "hub_tags": ["qualified"], "top10_firms": [],
        "already_screened": True,
        "prior_screen": {"date": "2026-07-20", "fitScore": 2.9, "gate": False,
                          "roundStage": "Series D"},
        "hub_url": "https://hub.example.com/docs/qualified-deals/beta",
    }
    d.update(over)
    return d


# ── the fit block, in EVERY flow ──────────────────────────────────────────────

def test_new_deal_renders_its_fit_score_and_gate():
    html = ef.intake_email_html([_new_deal()], title="Top 10 VC Radar")
    assert "3.4" in html
    assert "CLEARS GATE" in html
    assert "Strong team, real revenue." in html
    # Dimension label resolved through the rubric, not printed as a raw key.
    assert ef.PARAM_LABELS.get("ai_score", "ai_score") in html


def test_title_is_whatever_the_flow_passes():
    """The renderer is flow-agnostic -- the same code path serves the weekly,
    Top 10 and watchlist emails, which is the point."""
    for title in ("Weekly Deal Flow", "Top 10 VC Radar", "Watchlist Update"):
        assert title in ef.intake_email_html([_new_deal()], title=title)


def test_hard_auto_pass_is_reported_over_the_tier_badge():
    html = ef.intake_email_html(
        [_new_deal(fit_hard_auto_pass=True, fit_gate=False,
                   fit_hard_auto_pass_reason="No meaningful AI component.")],
        title="X")
    assert "HARD AUTO-PASS" in html
    assert "No meaningful AI component." in html


def test_scoring_failure_is_never_rendered_as_a_pass():
    html = ef.intake_email_html(
        [_new_deal(fit_tier="error", fit_gate=False, fit_score=0.0)], title="X")
    assert "SCORING FAILED" in html


# ── the re-seen section (the previously-invisible half) ───────────────────────

def test_reseen_deal_appears_with_its_prior_score():
    html = ef.intake_email_html([_reseen_deal()], title="X")
    assert "Already in Attio" in html
    assert "2.9" in html
    assert "screened 2026-07-20" in html


def test_reseen_deal_is_not_reported_as_freshly_screened():
    html = ef.intake_email_html([_reseen_deal()], title="X")
    # No fresh-screen framing for a deal we deliberately did not re-research.
    assert "Deal Screen" not in html
    assert "Rationale." not in html


def test_new_and_reseen_are_separated_and_counted():
    html = ef.intake_email_html([_new_deal(), _reseen_deal()], title="X")
    assert "1 new" in html
    assert "1 already in Attio" in html
    assert html.index("Acme AI") < html.index("Already in Attio")


def test_reseen_without_a_prior_score_still_renders():
    """A company on file in Attio but with no screen summary yet -- must not
    crash or print 'None'."""
    html = ef.intake_email_html(
        [_reseen_deal(prior_screen={"date": "2026-07-20"})], title="X")
    assert "Already in Attio" in html
    assert "None" not in html


# ── placement + Top 10, surfaced ─────────────────────────────────────────────

def test_series_b_dual_placement_is_shown_explicitly():
    """Attio can only display one stage, so the email is where the dual
    Qualified+Radar placement actually becomes visible."""
    html = ef.intake_email_html([_new_deal()], title="X")
    assert "Qualified + Radar" in html


def test_single_stage_shows_just_that_stage():
    html = ef.intake_email_html(
        [_new_deal(hub_tags=["qualified"], stage="Qualified")], title="X")
    assert "Qualified + Radar" not in html


def test_top10_firms_are_named():
    html = ef.intake_email_html([_new_deal()], title="X")
    assert "Sequoia Capital, Index Ventures" in html


def test_no_top10_badge_when_no_tier1_on_the_cap_table():
    html = ef.intake_email_html([_new_deal(top10_firms=[])], title="X")
    assert "Top 10 VC</span>" not in html


# ── robustness ────────────────────────────────────────────────────────────────

def test_empty_deal_list_renders_a_valid_email():
    html = ef.intake_email_html([], title="Weekly Deal Flow")
    assert "Weekly Deal Flow" in html
    assert "No deals in this export." in html


def test_html_is_escaped():
    html = ef.intake_email_html([_reseen_deal()], title="X")
    assert "Bain &amp; Company" in html
    assert "Bain & Company" not in html.replace("Bain &amp; Company", "")


def test_injected_markup_in_a_company_name_is_neutralized():
    html = ef.intake_email_html(
        [_new_deal(company="<script>alert(1)</script>")], title="X")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_tags_are_balanced():
    """A malformed table nest renders as a visible staircase in mail clients
    even when every string assertion above passes."""
    html = ef.intake_email_html([_new_deal(), _reseen_deal()], title="X")
    void = {"br", "img", "hr", "meta", "input"}
    stack = []
    for closing, name, selfclose in re.findall(r'<(/?)(\w+)[^>]*?(/?)>', html):
        if name in void or selfclose:
            continue
        if closing:
            assert stack and stack[-1] == name, f"mismatched </{name}>, open: {stack[-3:]}"
            stack.pop()
        else:
            stack.append(name)
    assert stack == [], f"unclosed tags: {stack}"


def test_no_unrendered_placeholders():
    html = ef.intake_email_html([_new_deal(), _reseen_deal()], title="X")
    assert not re.findall(r'\{[a-z_]+\}', html)


def test_highest_score_first_within_each_section():
    high = _new_deal(company="HighCo", fit_score=3.9)
    low = _new_deal(company="LowCo", fit_score=1.2, fit_gate=False)
    html = ef.intake_email_html([low, high], title="X")
    assert html.index("HighCo") < html.index("LowCo")


def test_unscored_new_deals_sort_last_and_do_not_crash():
    scored = _new_deal(company="ScoredCo")
    unscored = _new_deal(company="UnscoredCo", fit_score=None, fit_params=[],
                          fit_gate=False)
    html = ef.intake_email_html([unscored, scored], title="X")
    assert html.index("ScoredCo") < html.index("UnscoredCo")


# ── plain-text fallback ───────────────────────────────────────────────────────

def test_text_version_covers_both_sections():
    txt = ef.intake_email_text([_new_deal(), _reseen_deal()], title="Top 10 VC Radar")
    assert "Top 10 VC Radar" in txt
    assert "— NEW —" in txt
    assert "— ALREADY IN ATTIO —" in txt
    assert "fit 3.4/4.0" in txt
    assert "already screened 2.9/4.0" in txt
    assert "[CLEARS GATE]" in txt


def test_text_version_handles_an_empty_list():
    assert ef.intake_email_text([], title="X").startswith("X")
