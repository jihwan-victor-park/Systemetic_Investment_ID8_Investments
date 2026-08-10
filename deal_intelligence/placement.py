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

