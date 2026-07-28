"""Radar's mandate screen (RADAR_PLAN.md Part I §1.3, Part IV guardrail #1).

Because ID8 co-invests, most companies on Radar can be ruled out before any
sensor budget is spent on them. Four deterministic screens, applied in
order -- S1 geography, S2 next round in mandate, S3 Tier 1 on the cap table
(the important one, a hard gate per RADAR_PLAN.md Part IV #1), S4 not a
bridge/flat round. `mandatePass = S1 and S2 and S3 and S4`; a company that
fails is recorded with a reason and never sensed again (radar_state.py's
short-circuit).

Same pure-function idiom as rubric.py: plain data in, plain data out, no I/O
in this module at all -- unit-testable with zero mocking. Firestore/Attio
reads happen in radar_state.py, which calls this module's `screen()`.
"""
import re

# Same pattern portfolio_prefilter._classify_region uses, duplicated rather
# than imported: portfolio_prefilter.py has no public region classifier
# (leading underscore), and this module is deliberately self-contained pure
# logic with zero cross-module coupling, matching rubric.py's own isolation.
US_STATE_ABBREVS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
NA_COUNTRIES = {"united states", "usa", "u.s.", "u.s.a.", "canada", "mexico"}
EUROPE_COUNTRIES = {
    "united kingdom", "uk", "ireland", "france", "germany", "spain", "italy",
    "netherlands", "belgium", "switzerland", "austria", "sweden", "norway",
    "denmark", "finland", "portugal", "poland", "czech republic", "greece",
    "luxembourg", "iceland", "estonia", "latvia", "lithuania", "hungary",
    "romania", "bulgaria", "croatia", "slovenia", "slovakia",
}

# Same regex pipeline/app.py's determine_stage uses to route Series B-or-below
# to Radar (_BELOW_MANDATE_SERIES_RE) -- duplicated here rather than imported
# because deal_intelligence never imports from pipeline (the dependency runs
# the other way: pipeline/app.py imports deal_intelligence, see its own
# `from deal_intelligence import ...` block). A company already routed to
# Radar should always pass S2, but the mandate screen re-checks it anyway so
# it stays self-contained and auditable on its own, independent of how the
# company arrived. Keep in sync with pipeline/app.py's copy if either changes.
_BELOW_MANDATE_SERIES_RE = re.compile(
    r'^\s*(?:pre[-\s]?seed|seed|angel|pre[-\s]?a|series\s*[ab]\d*)\b', re.IGNORECASE)

_BRIDGE_KEYWORDS = ("bridge", "extension", "convertible", "safe", "flat")

# v1 heuristic floor: a round below this fraction of what's typical for its
# series reads as a bridge/extension rather than a primary round. Deliberately
# rough -- see the plan's own risk #2: PitchBook's real `Deal Type` column
# (Bridge Loan / Later Stage VC / etc.) would make this reliable and is
# dropped at intake (pipeline/app.py's DROP_COLS). Values in real dollars.
_SERIES_SIZE_FLOOR = {"seed": 1_000_000, "a": 5_000_000, "b": 15_000_000}


def classify_region(hq_location):
    """hqLocation is free text ("San Francisco, CA" / "London, United
    Kingdom"), not a region code. Returns "NA", "Europe", "other", or None
    (unparseable -- treated as unknown, not excluded)."""
    if not hq_location or "," not in hq_location:
        return None
    tail = hq_location.rsplit(",", 1)[-1].strip()
    tail_lc = tail.lower()
    if tail.upper() in US_STATE_ABBREVS:
        return "NA"
    if tail_lc in NA_COUNTRIES:
        return "NA"
    if tail_lc in EUROPE_COUNTRIES:
        return "Europe"
    return "other"


def build_tier1_index(top_vcs):
    """Python mirror of hub-next's companyIndex.buildInvestorIndex(tier1, [])
    -- Top 10 VC list ONLY per Oscar's confirmed scope decision (partners are
    never passed in here, unlike the JS original which also indexes partner
    VCs for the hub's cross-reference column). top_vcs: the `topVCs`
    Firestore collection's docs, each shaped
    {name, deals: [{company, ...}], ...}. Returns
    {company_name.lower().strip(): [firm_name, ...]}. Built once per run
    (backfill/daily scan job), not per company -- same O(1)-lookup reasoning
    as the JS original, see this module's docstring."""
    index = {}
    for firm in top_vcs or []:
        firm_name = firm.get("name")
        if not firm_name:
            continue
        seen = set()
        for deal in firm.get("deals") or []:
            name_lc = (deal.get("company") or "").strip().lower()
            if not name_lc or name_lc in seen:
                continue
            seen.add(name_lc)
            index.setdefault(name_lc, []).append(firm_name)
    return index


def s1_geography(hq_location):
    """NA or Europe only, per the fund thesis's own screen (same rule
    portfolio_prefilter.py already applies to partner-VC portfolios)."""
    region = classify_region(hq_location)
    if region in ("NA", "Europe"):
        return True, None
    if region is None:
        # Unparseable/unknown HQ doesn't fail the screen -- same
        # "unknown, not excluded" convention portfolio_prefilter.py uses.
        return True, "S1 geography (unknown HQ, passed through)"
    return False, f"S1 geography: {hq_location!r} outside NA/Europe"


def s2_next_round_in_mandate(series):
    """The next round is in ID8's Series B+ mandate only if the CURRENT
    round is Series B or earlier -- a company already at Series C+ has no
    "next round" left to watch for co-investment (it's either already past
    where Radar tracks it, or it belongs in the live pipeline instead)."""
    if not series:
        return True, "S2 next round in mandate (unknown series, passed through)"
    if _BELOW_MANDATE_SERIES_RE.match(str(series)):
        return True, None
    return False, f"S2 next round in mandate: current round {series!r} is already past Series B"


def s3_tier1_on_cap_table(company_name, top10_vc_flag, tier1_index):
    """pass = top10_vc_flag OR a name match in tier1_index. The flag is
    OR'd in deliberately, not relied on alone: `topVCs[].deals[]` is a
    hand-typed admin list (unlike partner-VC portfolios, which are bulk
    PitchBook-imported), so a real Tier-1-backed company can miss the index
    by coverage gap alone. `top10VC` is set reliably at Attio-intake time
    straight from PitchBook's own Top 10 VC saved search, so it catches
    exactly the companies the index's coverage gap would otherwise silently
    hard-exclude -- see the plan's risk #1, this is the single highest-
    consequence gap in this build since an S3 fail is permanent."""
    name_lc = (company_name or "").strip().lower()
    firms = list(tier1_index.get(name_lc, [])) if name_lc else []
    passed = bool(top10_vc_flag) or bool(firms)
    if passed:
        return True, firms, None
    return False, firms, "S3 no Tier 1 on the cap table"


def s4_not_bridge_or_flat(series, deal_size):
    """v1 heuristic only (see module docstring's _SERIES_SIZE_FLOOR comment):
    series text naming a bridge/extension/convertible/SAFE/flat round, OR a
    deal size below the typical floor for its series. Weakest of the four
    screens in v1 -- flagged in the implementation plan as a candidate to
    demote rather than hard-gate, pending sign-off; ships as a hard gate for
    now per the confirmed spec."""
    series_lc = (series or "").lower()
    for kw in _BRIDGE_KEYWORDS:
        if kw in series_lc:
            return False, f"S4 not bridge/flat: series {series!r} names a {kw} round"
    if deal_size:
        for series_key, floor in _SERIES_SIZE_FLOOR.items():
            if series_key in series_lc and deal_size < floor:
                return False, f"S4 not bridge/flat: ${deal_size:,.0f} is below the typical {series_key.title()} floor"
    return True, None


def new_tier1_lead_likely(tier1_firms):
    """Deterministic proxy only -- no LLM, no research pass exists in this
    v1 (that's Phase 6). RADAR_PLAN.md §1.4's real read weighs six factors
    on each side (sector fit, fund-cycle position, growth metrics, etc.);
    this is just a count of Tier 1 firms already on the cap table, which is
    a reasonable first-order proxy (more Tier 1s on the table -> more
    competition/access for the next round) but genuinely thin. Refine once
    Phase 6's research pass exists -- flagged, not overstated."""
    n = len(tier1_firms)
    if n >= 2:
        return "high", f"{n} Tier 1 firms already on the cap table"
    if n == 1:
        return "medium", "1 Tier 1 firm on the cap table"
    return "low", "no Tier 1 firm on the cap table"  # unreachable when S3 passed via index alone, but reachable via the top10VC-flag path


def insider_round_risk(new_tier1_level, s4_pass):
    """Inverse-ish read of the same two inputs S1.4's `newTier1LeadLikely`
    and S4 already computed -- not a fifth independent factor."""
    if not s4_pass:
        return "high"
    if new_tier1_level == "high":
        return "low"
    return "medium"


def screen(fields, tier1_index):
    """The public entrypoint. fields: {name, hq, series, deal_size,
    top10VC}. Returns a plain dict shaped exactly like radar.mandate in
    RADAR_PLAN.md Part VIII's schema. Runs S1-S4 in order; mandatePass is
    all four; failReason is the FIRST screen that failed (S1 before S2
    before S3 before S4, matching RADAR_PLAN.md's own ordering) -- a company
    can fail more than one screen, but only the first is surfaced, same as
    a short-circuit `and` chain would naturally report."""
    name = fields.get("name")
    hq = fields.get("hq")
    series = fields.get("series")
    deal_size = fields.get("deal_size")
    top10_vc_flag = fields.get("top10VC")

    geo_pass, geo_reason = s1_geography(hq)
    round_pass, round_reason = s2_next_round_in_mandate(series)
    tier1_pass, tier1_firms, tier1_reason = s3_tier1_on_cap_table(name, top10_vc_flag, tier1_index)
    bridge_pass, bridge_reason = s4_not_bridge_or_flat(series, deal_size)

    checks = [
        (geo_pass, geo_reason),
        (round_pass, round_reason),
        (tier1_pass, tier1_reason),
        (bridge_pass, bridge_reason),
    ]
    mandate_pass = geo_pass and round_pass and tier1_pass and bridge_pass
    fail_reason = next((reason for passed, reason in checks if not passed), None)

    new_tier1_level, new_tier1_reasoning = new_tier1_lead_likely(tier1_firms)
    insider_risk = insider_round_risk(new_tier1_level, bridge_pass)

    reasoning_parts = [
        f"{hq or 'unknown HQ'} ({classify_region(hq) or 'unknown region'})",
        # `series` already carries its own "Series" prefix for lettered
        # rounds (PitchBook's raw values, e.g. "Series B") but not for
        # Seed/Pre-Seed/Angel -- so this reads correctly either way without
        # a second literal "Series" prepended (that produced a visible
        # "Series Series B" bug during a smoke test against real-shaped data).
        f"current round {series or 'unknown'} -> next round in mandate: {'yes' if round_pass else 'no'}",
        f"Tier 1 on cap table: {', '.join(tier1_firms) if tier1_firms else ('yes (Top 10 VC flag)' if top10_vc_flag else 'no')}",
        f"{'not a bridge/flat round' if bridge_pass else 'looks like a bridge/flat round'}",
    ]

    return {
        "pass": mandate_pass,
        "geoPass": geo_pass,
        "nextRoundInMandate": round_pass,
        "tier1OnCapTable": tier1_pass,
        "tier1Firms": tier1_firms,
        "top10VCFlag": bool(top10_vc_flag),
        "notBridgeOrFlat": bridge_pass,
        "newTier1LeadLikely": new_tier1_level,
        "insiderRoundRisk": insider_risk,
        "reasoning": " · ".join(reasoning_parts),
        "failReason": fail_reason,
    }
