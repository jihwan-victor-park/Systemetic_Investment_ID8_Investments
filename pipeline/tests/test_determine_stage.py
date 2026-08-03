"""Covers determine_stage's Series B-or-earlier -> Radar routing.

The original implementation matched an exact set ({'Seed', 'Pre-Seed', 'Pre-A',
'Series A'}), so every real-world PitchBook variant -- 'Series A1'/'Series A2'
(cited in ensure_select_option's own docstring as a value PitchBook sends),
'Seed Round', 'Angel', lowercase -- fell through to the caller's default stage
instead of Radar. These cases pin that.

Widened from Series A to Series B 2026-07-28 (RADAR_PLAN.md Part I): ID8
invests at Series B+, so a company that just closed its B can't raise again
for 18-24 months -- it belongs on Radar until its next round, not in the live
pipeline.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import determine_stage


@pytest.mark.parametrize("series", [
    "Seed", "Pre-Seed", "Pre Seed", "Preseed", "Pre-A", "Pre A", "Series A",
    "Series A1", "Series A2", "Series A3", "SeriesA",
    "Seed Round", "Seed round", "seed", "series a", "SERIES A2",
    "Angel", "Angel (individual)",
    "  Series A  ",
])
def test_below_series_b_routes_to_radar(series):
    assert determine_stage(series, "Qualified") == "Radar"


@pytest.mark.parametrize("series", [
    "Series B", "Series B1", "Series B2", "series b", "SERIES B2", "  Series B  ",
])
def test_series_b_now_lands_in_both_buckets(series):
    """Behaviour change, 2026-08-03. Series B used to route to Radar outright
    (the 07-28 widening below). Oscar's rule now puts a B in BOTH places: the
    caller's in-mandate stage in Attio (which can only hold one value) plus a
    `radar` tag on the hub side, since a company that just closed its B is
    simultaneously in-mandate at B+ and unable to raise again for 18-24 months.
    test_determine_placement.py owns the full matrix; this pins the
    single-stage wrapper's half of it."""
    from app import determine_placement
    assert determine_stage(series, "Qualified") == "Qualified"
    # 'radar' is the ADDITIVE tag; 'qualified' is the primary stage and is
    # deliberately not duplicated into tags (hub-next unions the two itself).
    assert determine_placement(series, "Qualified")[1] == ["radar"]


@pytest.mark.parametrize("series", [
    "Series C", "Series D", "Series E",
    "Series AA", "Series BB", "Growth", "Later Stage VC",
])
def test_series_c_and_later_keep_the_default_stage(series):
    assert determine_stage(series, "Qualified") == "Qualified"


@pytest.mark.parametrize("series", ["", "   ", None, "nan"])
def test_unknown_series_keeps_the_default_rather_than_demoting_to_radar(series):
    # We can't tell what stage it is, so don't silently demote it.
    assert determine_stage(series, "Qualified") == "Qualified"


def test_default_stage_is_returned_verbatim():
    assert determine_stage("Series C", "Watchlist") == "Watchlist"
