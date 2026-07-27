"""Covers determine_stage's Series A-or-earlier -> Radar routing.

The original implementation matched an exact set ({'Seed', 'Pre-Seed', 'Pre-A',
'Series A'}), so every real-world PitchBook variant -- 'Series A1'/'Series A2'
(cited in ensure_select_option's own docstring as a value PitchBook sends),
'Seed Round', 'Angel', lowercase -- fell through to the caller's default stage
instead of Radar. These cases pin that.
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
def test_series_a_or_earlier_routes_to_radar(series):
    assert determine_stage(series, "Qualified") == "Radar"


@pytest.mark.parametrize("series", [
    "Series B", "Series B1", "Series C", "Series D", "Series E",
    "series b", "Series AA", "Growth", "Later Stage VC",
])
def test_series_b_and_later_keep_the_default_stage(series):
    assert determine_stage(series, "Qualified") == "Qualified"


@pytest.mark.parametrize("series", ["", "   ", None, "nan"])
def test_unknown_series_keeps_the_default_rather_than_demoting_to_radar(series):
    # We can't tell what stage it is, so don't silently demote it.
    assert determine_stage(series, "Qualified") == "Qualified"


def test_default_stage_is_returned_verbatim():
    assert determine_stage("Series C", "Watchlist") == "Watchlist"
