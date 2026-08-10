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
    # Radar is gated on the cap table as of 2026-08-10 -- below-B reaches it
    # only with a TOP10 firm on the round. test_determine_placement.py owns the
    # full routing matrix; these are the smoke cases.
    TOP10 = ["Sequoia Capital"]

    def test_below_b_series_with_a_top10_backer_moves_to_radar(self):
        for series in ("Seed", "Pre-Seed", "Pre-A", "Series A"):
            assert determine_stage(series, "Watchlist", self.TOP10) == "Radar"

    def test_below_b_series_without_a_top10_backer_has_no_home(self):
        for series in ("Seed", "Pre-Seed", "Pre-A", "Series A"):
            assert determine_stage(series, "Watchlist") is None

    def test_series_b_keeps_the_in_mandate_stage_and_gets_a_radar_tag(self):
        from app import determine_placement
        assert determine_stage("Series B", "Qualified", self.TOP10) == "Qualified"
        assert "radar" in determine_placement("Series B", "Qualified", self.TOP10)[1]

    def test_series_b_without_a_top10_backer_is_qualified_only(self):
        from app import determine_placement
        assert determine_stage("Series B", "Qualified") == "Qualified"
        assert determine_placement("Series B", "Qualified")[1] == []

    def test_later_series_keeps_the_provided_default(self):
        assert determine_stage("Series C", "Qualified") == "Qualified"
        assert determine_stage("Series D", "Watchlist") == "Watchlist"

    def test_strips_whitespace_before_matching(self):
        assert determine_stage("  Seed  ", "Watchlist", self.TOP10) == "Radar"


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
