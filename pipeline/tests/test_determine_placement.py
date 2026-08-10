"""Covers determine_placement's series-band + cap-table routing.

The rule (Oscar 2026-08-10). `default_stage` is the caller's in-mandate
destination; `top10_firms` is the PER-DEAL match against TOP10:
  - above B (C, D, E, growth, ...)  -> default stage
  - exactly B                       -> default stage, PLUS radar if Top 10-backed
  - B-or-below with a Top 10 VC     -> Radar, overriding the default
  - B-or-below with NO Top 10 VC    -> (None, []), skipped entirely
  - unknown/blank                   -> default stage, no tags

Two regressions are pinned here.

1. The Radar gate (2026-08-10). Radar used to take ANY below-B series
   regardless of who was on the cap table -- the per-deal Top 10 match existed
   but was computed after placement had already been decided, so it only ever
   decorated the email. Radar filled with seed and angel rounds; a Series B
   with no Top 10 backer got a radar tag it didn't earn.

2. The default-stage bug (2026-08-03). /process-top10 used to pass
   default_stage='Radar', and the old `'Radar' if <=B else default_stage`
   therefore returned 'Radar' for EVERY series including C/D/E -- so no Top 10
   VC deal ever reached Qualified. The 'Radar'-as-default cases below guard
   against that class of bug returning.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import determine_placement, determine_stage
from deal_intelligence.tier1_firms import TOP10_NAMES

TOP10 = ["Sequoia Capital"]
BELOW_B = [
    "Seed", "Pre-Seed", "Pre Seed", "Preseed", "Pre-A", "Pre A", "Series A",
    "Series A1", "Series A2", "Series A3", "SeriesA",
    "Seed Round", "Seed round", "seed", "series a", "SERIES A2",
    "Angel", "Angel (individual)", "  Series A  ",
]


def test_the_fixture_firm_is_really_in_the_top10_list():
    """Guards the whole file: if TOP10_NAMES is ever re-cut and drops Sequoia,
    every 'backed' case below would silently start testing the unbacked path."""
    assert TOP10[0] in TOP10_NAMES


# ── B or below, Top 10-backed -> Radar ────────────────────────────────────────

@pytest.mark.parametrize("series", BELOW_B)
def test_below_b_with_top10_routes_to_radar(series):
    # Radar is the PRIMARY stage here, so it is not also listed in tags --
    # hub-next expects the primary excluded from the additive array.
    assert determine_placement(series, "Qualified", TOP10) == ("Radar", [])
    # Overrides a Watchlist default too -- the series rule wins.
    assert determine_placement(series, "Watchlist", TOP10) == ("Radar", [])


@pytest.mark.parametrize("firm", TOP10_NAMES)
def test_every_top10_firm_opens_the_radar_gate(firm):
    """Any one of the ten is sufficient -- the gate is 'a Top 10 firm', not a
    specific one."""
    assert determine_placement("Series A", "Qualified", [firm]) == ("Radar", [])


# ── B or below, NOT Top 10-backed -> nowhere ──────────────────────────────────

@pytest.mark.parametrize("series", BELOW_B)
def test_below_b_without_top10_has_no_home(series):
    """THE 2026-08-10 regression test. A None stage tells run_pipeline to skip
    the deal entirely: no Attio record, no Perplexity spend, no hub page."""
    assert determine_placement(series, "Qualified") == (None, [])
    assert determine_placement(series, "Qualified", []) == (None, [])
    assert determine_placement(series, "Watchlist", None) == (None, [])


def test_a_non_top10_investor_does_not_open_the_gate():
    # An empty match list is what match_top10 returns for a cap table with no
    # Top 10 firm -- the caller passes the RESULT, never raw investor names.
    assert determine_placement("Series A", "Qualified", []) == (None, [])


# ── exactly B -> in mandate, radar only if Top 10-backed ──────────────────────

@pytest.mark.parametrize("series", [
    "Series B", "Series B1", "Series B2", "series b", "SERIES B2", "  Series B  ",
])
def test_series_b_with_top10_lands_in_both_buckets(series):
    stage, tags = determine_placement(series, "Qualified", TOP10)
    # Attio can only hold one stage; Oscar's call is Qualified (the actionable
    # pipeline view), with the hub carrying the dual truth via an additive tag.
    # 'qualified' is the PRIMARY so it must not be duplicated into tags --
    # hub-next computes membership as {stage} u tags.
    assert stage == "Qualified"
    assert tags == ["radar"]


@pytest.mark.parametrize("series", ["Series B", "Series B1", "series b"])
def test_series_b_without_top10_is_qualified_only(series):
    """B clears the B+ mandate on its own, so it is still filed -- it just
    fails the Radar gate and gets no tag."""
    assert determine_placement(series, "Qualified") == ("Qualified", [])


def test_series_b_keeps_a_watchlist_default_as_its_attio_stage():
    assert determine_placement("Series B", "Watchlist", TOP10) == ("Watchlist", ["radar"])
    assert determine_placement("Series B", "Watchlist") == ("Watchlist", [])


def test_series_b_does_not_duplicate_the_radar_tag():
    # A caller whose default already IS Radar must not list radar in tags too.
    assert determine_placement("Series B", "Radar", TOP10) == ("Radar", [])


# ── above B -> the caller's in-mandate stage, gate irrelevant ─────────────────

@pytest.mark.parametrize("series", [
    "Series C", "Series D", "Series E", "Series AA", "Series BB",
    "Growth", "Later Stage VC",
])
def test_above_b_uses_the_default_stage(series):
    assert determine_placement(series, "Qualified") == ("Qualified", [])
    assert determine_placement(series, "Watchlist") == ("Watchlist", [])
    # A Top 10 backer does NOT pull a later-stage deal onto Radar: Radar is for
    # companies that just raised at or below B and so can't raise again soon.
    assert determine_placement(series, "Qualified", TOP10) == ("Qualified", [])


@pytest.mark.parametrize("series", ["Series C", "Series D", "Series E", "Growth"])
def test_above_b_reaches_qualified_for_the_top10_pathway(series):
    """The 2026-08-03 regression test. /process-top10 passes 'Qualified' as its
    in-mandate default, so a Series C/D/E Top 10 VC deal lands in Qualified.
    Under the old code (default 'Radar') every one of these returned 'Radar'."""
    stage, tags = determine_placement(series, "Qualified", TOP10)
    assert stage == "Qualified"
    assert "radar" not in tags


# ── real-world spellings from the Attio export (2026-08-10) ───────────────────

@pytest.mark.parametrize("series", [
    "Bridge To Series B", "Bridge to Series A", "Pre-B SAFE", "Pre B",
    "Early Stage VC", "early stage vc",
])
def test_non_series_x_spellings_are_treated_as_below_b(series):
    """These 8 rows in the 336-row export matched none of the old patterns and
    fell through to Qualified -- a pre-B round filed as in-mandate."""
    assert determine_placement(series, "Qualified", TOP10) == ("Radar", [])
    assert determine_placement(series, "Qualified") == (None, [])


@pytest.mark.parametrize("series", ["Later Stage VC", "Series B SAFE", "Series B Secondary"])
def test_spellings_that_must_not_be_dragged_below_b(series):
    """'Later Stage VC' is above B. The two 'Series B ...' variants are real Bs
    and must keep matching the B branch, not the below-B one."""
    stage, _ = determine_placement(series, "Qualified", TOP10)
    assert stage == "Qualified"


@pytest.mark.parametrize("series", ["NEA", "Bridge", "Series 1"])
def test_unparseable_series_values_are_not_guessed_at(series):
    """'NEA' is an investor name that landed in the Series column. A bare
    'Bridge' names no round. Neither gets a fabricated band."""
    assert determine_placement(series, "Qualified") == ("Qualified", [])


# ── unknown series -> don't guess, and don't discard ───────────────────────────

@pytest.mark.parametrize("series", ["", "   ", None, "nan", "none", "NaN"])
def test_unknown_series_keeps_the_default_and_adds_no_tags(series):
    """An unreadable series must not be swept up by the new skip path -- we
    can't tell what it is, so it keeps the caller's default rather than being
    silently dropped from intake."""
    assert determine_placement(series, "Qualified") == ("Qualified", [])
    assert determine_placement(series, "Watchlist") == ("Watchlist", [])
    assert determine_placement(series, "Qualified", TOP10) == ("Qualified", [])


# ── the legacy wrapper stays behaviour-compatible ─────────────────────────────

@pytest.mark.parametrize("series,default,firms,expected", [
    ("Series A", "Qualified", TOP10, "Radar"),
    ("Series A", "Qualified", None,  None),
    ("Seed",     "Qualified", TOP10, "Radar"),
    ("Seed",     "Qualified", None,  None),
    ("Series B", "Qualified", None,  "Qualified"),
    ("Series C", "Qualified", None,  "Qualified"),
    ("Series C", "Watchlist", None,  "Watchlist"),
    ("",         "Qualified", None,  "Qualified"),
])
def test_determine_stage_wrapper_matches_placement(series, default, firms, expected):
    assert determine_stage(series, default, firms) == expected
    assert determine_stage(series, default, firms) == determine_placement(series, default, firms)[0]
