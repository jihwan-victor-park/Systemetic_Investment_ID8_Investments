"""Where one deal belongs -- the series + cap-table placement rule.

Lives here rather than in pipeline/app.py (where it grew up) because BOTH
intake paths need it and the dependency only runs one way: pipeline/app.py
imports deal_intelligence, never the reverse, so the Attio-CSV reconciler
(import_attio_deals_csv.py) could not have reused it in place. Duplicating
the rule into the reconciler was the obvious alternative and the wrong one --
two copies of a routing rule Oscar has now revised three times is exactly how
the intake paths drifted apart before.

pipeline/app.py re-exports determine_stage/determine_placement, so
`from app import determine_placement` keeps working unchanged.
"""
import re

# Widened from "Series A or earlier" to "Series B or earlier" 2026-07-28
# (Oscar: "Radar should include Series B") -- see RADAR_PLAN.md Part I. ID8
# invests at Series B+, so a company that just closed a B can't raise again
# for 18-24 months: it isn't a live opportunity, it's a company to watch
# until its *next* round (the one actually in mandate). Renamed from
# _EARLY_SERIES_RE since "early" stopped being accurate once B was in scope
# -- this is "below where we'd write a check today", not "early-stage".
#
# Anchored at the start so 'Series B' matches but 'Series C' never does, and
# \d* after the letter covers the A1/A2/B1/B2 tranche naming. The trailing
# boundary stops 'Series BB'-style values from matching on the 'B'.
#
# The non-'Series X' spellings were added 2026-08-10, from a 336-row Attio
# export in which 8 companies carried values none of these patterns matched and
# so fell through to the caller's in-mandate default -- i.e. a pre-B round was
# being filed as Qualified. 'Later Stage VC' deliberately still doesn't match
# (it IS above B); a bare 'Bridge' with no round named, and junk like an
# investor name landing in the Series column ('NEA'), stay unmatched on purpose
# and keep the unknown-series default rather than being guessed at.
_BELOW_MANDATE_SERIES_RE = re.compile(
    r'^\s*(?:pre[-\s]?seed|seed|angel'
    r'|pre[-\s]?[ab]'                   # 'Pre-A', 'Pre-B SAFE'
    r'|early[-\s]stage'                 # PitchBook's generic early bucket
    r'|bridge\s+to\s+series\s*[ab]'     # a bridge TO a round hasn't closed it
    r'|series\s*[ab]\d*)\b',
    re.IGNORECASE)

# Series B specifically (B, B1, B2, ... but never 'BB'). Split out from
# _BELOW_MANDATE_SERIES_RE 2026-08-03: B is no longer just "below mandate", it
# is the one band that belongs in BOTH buckets -- see determine_placement.
_SERIES_B_RE = re.compile(r'^\s*series\s*b\d*\b', re.IGNORECASE)

QUALIFIED_STAGE = 'Qualified'


def determine_stage(series, default_stage, top10_firms=None):
    """Legacy single-stage resolver, kept for the callers and tests that only
    need "where does this one deal live in Attio". Prefer determine_placement,
    which also reports the hub's additive tags.

    A blank/unknown series is NOT treated as early -- we can't tell, so it keeps
    the caller's default rather than being silently demoted to Radar.

    Can now return None, meaning "this deal has no home" -- see
    determine_placement's Radar gate."""
    return determine_placement(series, default_stage, top10_firms)[0]


def determine_placement(series, default_stage, top10_firms=None):
    """Resolve one deal's placement from its series AND its cap table. Returns
    (attio_stage, hub_tags), where attio_stage is None for a deal that belongs
    nowhere and should be skipped entirely.

    hub_tags holds the ADDITIVE, non-primary hub stages only -- never the
    primary itself. hub-next models multi-stage membership as
    `checked = {stage} ∪ (tags ∩ PUBLIC_STAGES)` and expects the primary not to
    be duplicated inside `tags` (see StageMultiSelect.jsx's header comment and
    lib/stages.js's TAGS comment). A company shows up in a tab when EITHER its
    stage matches OR its tags contain that tab, so returning ['radar'] alongside
    stage='Qualified' is what puts one deal in both Qualified Deals and Radar.

    The rule, per Oscar 2026-08-10, is a property of the series AND of whether
    a TOP10 firm is on the cap table (`top10_firms`, the per-deal match from
    deal_intelligence.tier1_firms.match_top10 -- NOT the route-level
    /process-top10 flag). `default_stage` is the caller's in-mandate
    destination (Qualified for the deal-flow and Top 10 VC drops, Watchlist for
    the watchlist drop):
      - above B (C, D, E, growth, ...)  -> default stage
      - exactly B (B, B1, B2)           -> default stage, PLUS radar if Top 10-backed
      - B-or-below with a Top 10 VC     -> Radar, overriding the default
      - B-or-below with NO Top 10 VC    -> (None, []) -- skipped entirely
      - unknown/blank                   -> default stage, no tags

    Radar is now GATED ON THE CAP TABLE, which is the 2026-08-10 change. It
    previously took any below-B series regardless of investor, so Radar filled
    up with seed and angel rounds nobody was tracking, while the per-deal Top 10
    match this function now consumes was computed in run_pipeline and used only
    to decorate the email. Oscar's rule: Radar is "B or under, backed by one of
    our Top 10" -- a company worth watching precisely because a firm we rate
    just took a position and it can't raise again for 18-24 months.

    A None stage means "no home": below mandate and no Top 10 signal, so there
    is nothing to file. run_pipeline skips it rather than inventing a bucket --
    no Attio deal, no Perplexity spend, no hub page. Skipped deals are reported
    in results['filtered'] and in the intake email, never dropped silently.

    The dual case is why this function exists. Attio's `stage` is a
    single-select and cannot hold two values, so a Top 10-backed Series B
    resolves to the caller's stage in Attio (Oscar's call: for the
    deal-flow/Top 10 pathways that means **Qualified** -- Attio stays the
    actionable pipeline view) while the hub carries the full truth by ALSO
    tagging it `radar`. Such a Series B genuinely is both: in-mandate at B+,
    and simultaneously a company that just raised. A Series B WITHOUT a Top 10
    backer is Qualified only -- it clears the B+ mandate but fails the Radar
    gate.

    Radar is reached through the SERIES rule, never by an endpoint defaulting
    to it. That distinction is the fix for a real bug: /process-top10 used to
    pass default_stage='Radar', and `'Radar' if <=B else default_stage`
    therefore returned 'Radar' for EVERY series including C/D/E -- every Top
    10 VC deal landed on Radar and none ever reached Qualified. The old
    signature made that invisible to tests, which only ever passed
    'Qualified'/'Watchlist' as the default. Keeping the default as the
    in-mandate stage also leaves /process-watchlist's own Watchlist
    destination intact rather than forcing everything to Qualified.
    """
    s = str(series or '')
    has_top10 = bool(top10_firms)
    if _SERIES_B_RE.match(s):
        # In mandate at B+ regardless. The dual case -- primary stage plus an
        # additive radar tag -- now requires a Top 10 backer as well.
        if has_top10 and str(default_stage or '').strip().lower() != 'radar':
            return default_stage, ['radar']
        return default_stage, []
    if _BELOW_MANDATE_SERIES_RE.match(s):
        # A and below (B was handled above). Radar only with a Top 10 backer;
        # otherwise this deal has no home at all.
        return ('Radar', []) if has_top10 else (None, [])
    if s.strip() and s.strip().lower() not in ('nan', 'none'):
        # A known series above B -> the caller's in-mandate destination.
        return default_stage, []
    # Unknown series: we can't tell, so don't guess -- keep the caller's
    # default and add no tags.
    return default_stage, []


# ── Reconciliation view (deal_sync.py) ───────────────────────────────────────
# Everything below answers a DIFFERENT question from determine_placement.
# determine_placement asks "an intake file just handed me this row -- where do I
# file it?", and its answer depends on the caller's own destination
# (`default_stage`: Qualified for the deal-flow drop, Watchlist for the
# watchlist drop). The reconciler has no caller destination: it is looking at a
# deal that already exists on one or both sides and asking "given only the
# series and the cap table, where SHOULD this live?". So the in-mandate bucket
# has to be derived rather than passed in, which is what expected_placement
# does -- and deriving it is what surfaces the extra condition Oscar stated
# 2026-08-13: Qualified requires a **Tier 1 (33)** firm in the round, which
# determine_placement never checks because its caller had already decided.
#
# These are deliberately NOT merged into determine_placement. Doing so would
# change live intake: every above-B deal without a Tier 1 (33) match would stop
# resolving to Qualified and start resolving to nothing, silently dropping deals
# the pipeline files today. The reconciler only reports, so it can hold the
# stricter rule without that blast radius.

BAND_BELOW_B = 'below_b'
BAND_B = 'b'
BAND_ABOVE_B = 'above_b'
BAND_UNKNOWN = 'unknown'


def series_band(series):
    """Which of the four series bands a raw Attio/PitchBook Series value falls
    in. Shares the exact regexes determine_placement matches on, so the
    reconciler can never disagree with intake about what 'Series B1' or
    'Pre-Seed' means -- the two paths differ on the RULE, never on the parse."""
    s = str(series or '')
    if _SERIES_B_RE.match(s):
        return BAND_B
    if _BELOW_MANDATE_SERIES_RE.match(s):
        return BAND_BELOW_B
    if s.strip() and s.strip().lower() not in ('nan', 'none'):
        return BAND_ABOVE_B
    return BAND_UNKNOWN


def expected_placement(series, top10_firms=None, tier1_33_firms=None,
                       series_b_mode='dual'):
    """Where a deal SHOULD live given only its series and its cap table, as a
    (stage, hub_tags, reason) triple. `stage` is None for "no automatic home"
    -- which here means "the rule doesn't place it", not "delete it": a deal
    already filed by hand in Attio (Invested, Passed, a Target someone is
    working) legitimately has no rule-derived home, and the reconciler reports
    those separately rather than proposing to move them.

    Oscar's rule, 2026-08-13:
      - a Tier 1 (33) firm in the round AND above Series B  -> Qualified
      - Series B or below AND a Top 10 firm in the round    -> Radar

    `series_b_mode` exists because exactly-Series-B is the one band those two
    clauses disagree on, and the shipped code already took a side:
      - 'dual' (default, = what determine_placement does today): a Top 10-backed
        Series B is Qualified in Attio AND carries the additive `radar` tag in
        the hub. It clears the B+ mandate and it just raised, so it is honestly
        both, and Attio's single-select stage can only hold the actionable one.
      - 'radar': reads "Series B or less -> Radar" literally, so a Top 10-backed
        Series B is Radar only, never Qualified.
    deal_sync reports the population affected by this choice under its own
    heading so the difference is a decision Oscar makes on real numbers rather
    than one buried in a default.
    """
    band = series_band(series)
    has_top10 = bool(top10_firms)
    has_tier1_33 = bool(tier1_33_firms) or has_top10   # TOP10 is a subset of the 33

    if band == BAND_ABOVE_B:
        if has_tier1_33:
            return QUALIFIED_STAGE, [], 'above Series B with a Tier 1 (33) investor'
        return None, [], 'above Series B but no Tier 1 (33) investor on the cap table'

    if band == BAND_B:
        if has_top10:
            if series_b_mode == 'radar':
                return 'Radar', [], 'Series B with a Top 10 investor (series-b-mode=radar)'
            return QUALIFIED_STAGE, ['radar'], 'Series B with a Top 10 investor (in mandate at B+, and just raised)'
        if has_tier1_33:
            # Not above B, so the Qualified clause does not fire on its own;
            # not Top 10-backed, so the Radar gate does not either.
            return None, [], 'Series B with a Tier 1 (33) but no Top 10 investor'
        return None, [], 'Series B with no Tier 1 (33) or Top 10 investor'

    if band == BAND_BELOW_B:
        if has_top10:
            return 'Radar', [], 'below Series B with a Top 10 investor'
        return None, [], 'below Series B with no Top 10 investor'

    return None, [], 'series unknown -- cannot place from the rule'

