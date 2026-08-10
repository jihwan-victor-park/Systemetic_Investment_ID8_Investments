"""Covers determine_stage, the single-stage wrapper over determine_placement.

The original implementation matched an exact set ({'Seed', 'Pre-Seed', 'Pre-A',
'Series A'}), so every real-world PitchBook variant -- 'Series A1'/'Series A2'
(cited in ensure_select_option's own docstring as a value PitchBook sends),
'Seed Round', 'Angel', lowercase -- fell through to the caller's default stage
instead of Radar. Those spelling cases are still pinned here; what CHANGED
2026-08-10 is that matching the below-B band is no longer sufficient on its own.

Radar is now gated on the cap table (Oscar 2026-08-10): B-or-under reaches Radar
only when one of the TOP10 firms is on it. Without that, the deal has no home
and determine_stage returns None. test_determine_placement.py owns the full
matrix including the tags; this file pins the wrapper's half.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import determine_placement, determine_stage

TOP10 = ["Sequoia Capital"]        # a real TOP10_NAMES entry
BELOW_B = [
    "Seed", "Pre-Seed", "Pre Seed", "Preseed", "Pre-A", "Pre A", "Series A",
    "Series A1", "Series A2", "Series A3", "SeriesA",
    "Seed Round", "Seed round", "seed", "series a", "SERIES A2",
    "Angel", "Angel (individual)",
    "  Series A  ",
]


@pytest.mark.parametrize("series", BELOW_B)
def test_below_b_with_a_top10_backer_routes_to_radar(series):
    assert determine_stage(series, "Qualified", TOP10) == "Radar"


@pytest.mark.parametrize("series", BELOW_B)
def test_below_b_without_a_top10_backer_has_no_home(series):
    """The 2026-08-10 gate. These used to land on Radar unconditionally, which
    filled it with seed and angel rounds nobody was tracking."""
    assert determine_stage(series, "Qualified") is None
    assert determine_stage(series, "Qualified", []) is None


@pytest.mark.parametrize("series", [
    "Series B", "Series B1", "Series B2", "series b", "SERIES B2", "  Series B  ",
])
def test_series_b_is_in_mandate_with_or_without_a_top10_backer(series):
    """B clears the B+ mandate on its own -- the Top 10 gate only decides
    whether it ALSO gets the radar tag, never whether it's filed at all."""
    assert determine_stage(series, "Qualified", TOP10) == "Qualified"
    assert determine_stage(series, "Qualified") == "Qualified"
    assert determine_placement(series, "Qualified", TOP10)[1] == ["radar"]
    assert determine_placement(series, "Qualified")[1] == []


@pytest.mark.parametrize("series", [
    "Series C", "Series D", "Series E",
    "Series AA", "Series BB", "Growth", "Later Stage VC",
])
def test_series_c_and_later_keep_the_default_stage(series):
    assert determine_stage(series, "Qualified") == "Qualified"
    assert determine_stage(series, "Qualified", TOP10) == "Qualified"


@pytest.mark.parametrize("series", ["", "   ", None, "nan"])
def test_unknown_series_keeps_the_default_rather_than_being_dropped(series):
    # We can't tell what stage it is, so don't silently demote OR discard it.
    assert determine_stage(series, "Qualified") == "Qualified"
    assert determine_stage(series, "Qualified", TOP10) == "Qualified"


def test_default_stage_is_returned_verbatim():
    assert determine_stage("Series C", "Watchlist") == "Watchlist"
