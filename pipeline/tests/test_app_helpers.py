"""Unit tests for pipeline/app.py's pure helper functions -- clean_number,
determine_stage, and the HUB_STAGE_TO_ATTIO_TITLE mapping the new
/update-deal-stage endpoint uses. pipeline/ has no __init__.py, so import
`app` by adding this directory to sys.path directly, same pattern as
lp-screener/tests. Importing the module itself is safe with no credentials
configured -- verified manually; nothing at module scope requires a live
Firestore/Attio/GCS client."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import HUB_STAGE_TO_ATTIO_TITLE, clean_number, determine_stage  # noqa: E402


class TestCleanNumber:
    def test_plain_number(self):
        assert clean_number(400) == 400.0

    def test_strips_currency_formatting(self):
        assert clean_number("$1,163.11") == 1163.11

    def test_none_and_nan_are_none(self):
        assert clean_number(None) is None
        assert clean_number(float("nan")) is None
        assert clean_number(pd.NA) is None

    def test_unparseable_string_is_none_not_an_exception(self):
        assert clean_number("not a number") is None


class TestDetermineStage:
    def test_below_b_series_moves_to_radar(self):
        # Widened from Series A to Series B 2026-07-28 -- RADAR_PLAN.md Part I.
        # Narrowed back to "below B" 2026-08-03: Series B is no longer Radar-only,
        # it lands in BOTH buckets (the caller's in-mandate stage in Attio, plus a
        # `radar` hub tag) per Oscar's confirmed rules. See
        # test_determine_placement.py, which owns the full routing matrix.
        for series in ("Seed", "Pre-Seed", "Pre-A", "Series A"):
            assert determine_stage(series, "Watchlist") == "Radar"

    def test_series_b_keeps_the_in_mandate_stage_and_gets_a_radar_tag(self):
        from app import determine_placement
        assert determine_stage("Series B", "Qualified") == "Qualified"
        assert "radar" in determine_placement("Series B", "Qualified")[1]

    def test_later_series_keeps_the_provided_default(self):
        assert determine_stage("Series C", "Qualified") == "Qualified"
        assert determine_stage("Series D", "Watchlist") == "Watchlist"

    def test_strips_whitespace_before_matching(self):
        assert determine_stage("  Seed  ", "Watchlist") == "Radar"


class TestHubStageToAttioTitle:
    def test_covers_every_hub_next_stage_key(self):
        # Keep this in sync with hub-next/src/lib/stages.js's PUBLIC_STAGES --
        # a stage the hub can assign that this map can't translate would
        # make /update-deal-stage silently 400 on a real user action.
        assert set(HUB_STAGE_TO_ATTIO_TITLE) == {
            "watchlist", "pipeline", "qualified", "radar", "invested",
        }

    def test_values_are_title_case_matching_existing_attio_writes(self):
        # e.g. build_attio_values/fix_radar_stages already write "Radar",
        # "Qualified", "Watchlist" this same way -- must stay consistent.
        assert HUB_STAGE_TO_ATTIO_TITLE["radar"] == "Radar"
        assert HUB_STAGE_TO_ATTIO_TITLE["qualified"] == "Qualified"
        assert HUB_STAGE_TO_ATTIO_TITLE["watchlist"] == "Watchlist"
