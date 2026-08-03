"""Covers determine_placement's series-band routing (Oscar's rules, 2026-08-03).

The rule is a property of the SERIES, applied identically to every intake
source; `default_stage` is the caller's in-mandate destination:
  - below B  -> Radar, overriding the default
  - exactly B -> default stage AND the radar tag (the dual case)
  - above B  -> default stage
  - unknown  -> default stage, no tags

The regression these pin: /process-top10 used to pass default_stage='Radar',
and the old `'Radar' if <=B else default_stage` therefore returned 'Radar' for
EVERY series including C/D/E -- so no Top 10 VC deal ever reached Qualified.
test_determine_stage.py could not catch it because it only ever passed
'Qualified'/'Watchlist' as the default. The 'Radar'-as-default cases below are
the direct guard against that class of bug returning.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import determine_placement, determine_stage


# ── below B -> Radar, whatever the default ────────────────────────────────────

@pytest.mark.parametrize("series", [
    "Seed", "Pre-Seed", "Pre Seed", "Preseed", "Pre-A", "Pre A", "Series A",
    "Series A1", "Series A2", "Series A3", "SeriesA",
    "Seed Round", "Seed round", "seed", "series a", "SERIES A2",
    "Angel", "Angel (individual)", "  Series A  ",
])
def test_below_b_routes_to_radar(series):
    # Radar is the PRIMARY stage here, so it is not also listed in tags --
    # hub-next expects the primary excluded from the additive array.
    assert determine_placement(series, "Qualified") == ("Radar", [])
    # Overrides a Watchlist default too -- the series rule wins.
    assert determine_placement(series, "Watchlist") == ("Radar", [])


# ── exactly B -> BOTH ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("series", [
    "Series B", "Series B1", "Series B2", "series b", "SERIES B2", "  Series B  ",
])
def test_series_b_lands_in_both_buckets(series):
    stage, tags = determine_placement(series, "Qualified")
    # Attio can only hold one stage; Oscar's call is Qualified (the actionable
    # pipeline view), with the hub carrying the dual truth via an additive tag.
    # 'qualified' is the PRIMARY so it must not be duplicated into tags --
    # hub-next computes membership as {stage} u tags.
    assert stage == "Qualified"
    assert tags == ["radar"]


def test_series_b_keeps_a_watchlist_default_as_its_attio_stage():
    stage, tags = determine_placement("Series B", "Watchlist")
    assert stage == "Watchlist"
    assert tags == ["radar"]


def test_series_b_does_not_duplicate_the_radar_tag():
    # A caller whose default already IS Radar must not list radar in tags too.
    assert determine_placement("Series B", "Radar") == ("Radar", [])


# ── above B -> the caller's in-mandate stage ──────────────────────────────────

@pytest.mark.parametrize("series", [
    "Series C", "Series D", "Series E", "Series AA", "Series BB",
    "Growth", "Later Stage VC",
])
def test_above_b_uses_the_default_stage(series):
    assert determine_placement(series, "Qualified") == ("Qualified", [])
    assert determine_placement(series, "Watchlist") == ("Watchlist", [])


@pytest.mark.parametrize("series", ["Series C", "Series D", "Series E", "Growth"])
def test_above_b_reaches_qualified_for_the_top10_pathway(series):
    """THE regression test. /process-top10 now passes 'Qualified' as its
    in-mandate default, so a Series C/D/E Top 10 VC deal lands in Qualified.
    Under the old code (default 'Radar') every one of these returned 'Radar'."""
    stage, tags = determine_placement(series, "Qualified")
    assert stage == "Qualified"
    assert "radar" not in tags


# ── unknown series -> don't guess ─────────────────────────────────────────────

@pytest.mark.parametrize("series", ["", "   ", None, "nan", "none", "NaN"])
def test_unknown_series_keeps_the_default_and_adds_no_tags(series):
    assert determine_placement(series, "Qualified") == ("Qualified", [])
    assert determine_placement(series, "Watchlist") == ("Watchlist", [])


# ── the legacy wrapper stays behaviour-compatible ─────────────────────────────

@pytest.mark.parametrize("series,default,expected", [
    ("Series A", "Qualified", "Radar"),
    ("Seed", "Qualified", "Radar"),
    ("Series C", "Qualified", "Qualified"),
    ("Series C", "Watchlist", "Watchlist"),
    ("", "Qualified", "Qualified"),
])
def test_determine_stage_wrapper_matches_placement(series, default, expected):
    assert determine_stage(series, default) == expected
    assert determine_stage(series, default) == determine_placement(series, default)[0]


def test_series_b_stage_changed_deliberately():
    """Documents the one intentional behaviour change vs the old
    determine_stage: Series B used to resolve to 'Radar' outright. It now
    resolves to the in-mandate stage plus a radar TAG, because Oscar wants a B
    in both places rather than only on Radar."""
    assert determine_stage("Series B", "Qualified") == "Qualified"
    assert "radar" in determine_placement("Series B", "Qualified")[1]


def test_tags_never_contain_the_primary_stage():
    """hub-next's StageMultiSelect reconciles {stage} u (tags n PUBLIC_STAGES)
    and treats the primary as absent from tags; duplicating it would double-count
    the stage in the checked set and render it twice."""
    for series in ("Seed", "Series A", "Series B", "Series C", "Growth", ""):
        for default in ("Qualified", "Watchlist", "Radar"):
            stage, tags = determine_placement(series, default)
            assert stage.lower() not in [t.lower() for t in tags], (series, default, stage, tags)
