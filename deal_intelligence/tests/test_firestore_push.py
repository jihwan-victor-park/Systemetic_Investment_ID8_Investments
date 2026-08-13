"""Unit tests for firestore_push's pure helpers -- no Firestore client is
constructed (importing the module is enough; _firestore() is lazy).

round_fields_patch is the shared Series/Deal Date/Deal Size merge rule used by
BOTH Attio -> hub write paths (push_company_from_attio and
import_attio_deals_csv), so a regression here silently reintroduces the
"Series column is an em-dash / Deal Date is stale" class of bug that deal_sync
had to keep repairing by hand.
"""
from deal_intelligence.firestore_push import round_fields_patch


class TestNewCompany:
    def test_writes_all_three_explicitly(self):
        patch = round_fields_patch(None, round_="Series B", round_date="2026-01-02", round_size=5_000_000)
        assert patch == {"round": "Series B", "roundDate": "2026-01-02", "roundSize": 5_000_000}

    def test_missing_attio_values_are_explicit_nulls_not_absent_keys(self):
        # Explicit None matters: hub-next's listCompanies() treats a genuinely
        # undefined field differently from a null one in places, and "imported,
        # Attio had nothing" should be legible in Firestore.
        assert round_fields_patch({}, round_="", round_date=None, round_size=None) == {
            "round": None, "roundDate": None, "roundSize": None,
        }


class TestExistingCompany:
    def test_fills_a_blank_series(self):
        # The 7-company bug: Attio has a Series, the hub shows an em-dash,
        # because the write only ever happened on creation.
        patch = round_fields_patch({"round": None}, round_="Series B")
        assert patch == {"round": "Series B"}

    def test_never_overwrites_a_series_the_hub_already_has(self):
        # Hand-editable in the hub, and disagreements run in both directions --
        # correcting one stays a human call (deal_sync --overwrite-series).
        assert round_fields_patch({"round": "Series C"}, round_="Series B") == {}

    def test_refreshes_a_stale_deal_date(self):
        # AMCA: hub held 2026-05-08 from an older import, Attio said 2026-08-12.
        patch = round_fields_patch({"roundDate": "2026-05-08"}, round_date="2026-08-12")
        assert patch == {"roundDate": "2026-08-12"}

    def test_iso_timestamp_and_plain_date_are_not_a_disagreement(self):
        assert round_fields_patch({"roundDate": "2026-08-12T00:00:00Z"}, round_date="2026-08-12") == {}

    def test_refreshes_a_stale_deal_size(self):
        assert round_fields_patch({"roundSize": 1_000_000}, round_size=5_000_000) == {"roundSize": 5_000_000}

    def test_numeric_and_string_sizes_are_not_a_disagreement(self):
        assert round_fields_patch({"roundSize": 5_000_000.0}, round_size="5000000") == {}

    def test_unparseable_sizes_fall_back_to_a_trimmed_string_compare(self):
        assert round_fields_patch({"roundSize": "$5M"}, round_size=" $5M ") == {}
        assert round_fields_patch({"roundSize": "$5M"}, round_size="$7M") == {"roundSize": "$7M"}

    def test_blank_attio_values_never_blank_a_known_value(self):
        existing = {"round": "Series B", "roundDate": "2026-01-02", "roundSize": 5_000_000}
        assert round_fields_patch(existing, round_="", round_date="", round_size=None) == {}
