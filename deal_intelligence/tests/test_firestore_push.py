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


class TestAdditionalRoundDocs:
    """A new round of a company the hub already has must land as its own doc,
    the way the bulk CSV import has always written them. Before 2026-08-13 the
    live webhook didn't do this, so a Series C arriving for a company sitting
    at Series B Secondary returned 200 and changed nothing visible."""

    def test_round_doc_id_matches_the_bulk_imports_shape(self):
        from deal_intelligence.firestore_push import round_doc_id
        assert round_doc_id("decart", "Series C") == "decart--series-c"

    def test_the_two_write_paths_cannot_drift(self):
        # import_attio_deals_csv._round_slug delegates to round_doc_slug --
        # if it ever stopped, the same round would land as two hub docs.
        from deal_intelligence.firestore_push import round_doc_slug
        from deal_intelligence.import_attio_deals_csv import _round_slug
        for series in ("Series C", "Series B Secondary", "Seed", None, ""):
            assert _round_slug(series) == round_doc_slug(series)

    def test_a_blank_series_falls_back_to_the_generic_slug(self):
        from deal_intelligence.firestore_push import round_doc_slug
        assert round_doc_slug(None) == "round"
        assert round_doc_slug("") == "round"

    def test_a_genuinely_new_round_is_flagged(self):
        from deal_intelligence.firestore_push import is_new_round
        assert is_new_round(False, "Series C", "Series B Secondary")

    def test_the_same_round_arriving_twice_is_not(self):
        from deal_intelligence.firestore_push import is_new_round
        assert not is_new_round(False, "Series C", "Series C")
        # Same round, different casing/spacing -- slugified, so still a match.
        assert not is_new_round(False, "series c", "Series C")

    def test_a_brand_new_company_never_gets_a_second_doc(self):
        # Its one round belongs on the base doc, not a sibling.
        from deal_intelligence.firestore_push import is_new_round
        assert not is_new_round(True, "Series C", None)

    def test_a_round_the_base_doc_just_adopted_is_not_a_new_round(self):
        # round_fields_patch fills a blank Series on this same push, so the
        # comparison runs against the post-patch value. Comparing against the
        # stale blank would create a redundant decart--series-c alongside a
        # base doc that now says Series C.
        from deal_intelligence.firestore_push import is_new_round
        assert not is_new_round(False, "Series C", "Series C")

    def test_a_deal_with_no_series_is_never_a_new_round(self):
        from deal_intelligence.firestore_push import is_new_round
        assert not is_new_round(False, None, "Series B")
        assert not is_new_round(False, "", "Series B")
