"""Unit tests for the Attio <-> hub reconciler.

Everything here runs on fabricated dicts -- no Firestore, no Attio, no CSV on
disk except where the parser itself is under test. The two I/O-shaped functions
(dump_attio_snapshot / dump_hub_snapshot) are deliberately not covered: they are
thin paginate-and-write wrappers, and the shapes they produce are what the pure
functions below are tested against.
"""
import pytest

from deal_intelligence import deal_sync as ds
from deal_intelligence.placement import (BAND_ABOVE_B, BAND_B, BAND_BELOW_B,
                                         BAND_UNKNOWN, expected_placement,
                                         series_band)

TOP10 = ["Sequoia Capital"]
TIER33 = ["Battery Ventures"]


# ── series bands ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("series,band", [
    ("Series C", BAND_ABOVE_B), ("Series H", BAND_ABOVE_B), ("Later Stage VC", BAND_ABOVE_B),
    ("Series B", BAND_B), ("Series B2", BAND_B), ("series b1", BAND_B),
    ("Series A", BAND_BELOW_B), ("Seed", BAND_BELOW_B), ("Pre-Seed", BAND_BELOW_B),
    ("Early Stage VC", BAND_BELOW_B), ("Angel", BAND_BELOW_B),
    ("", BAND_UNKNOWN), (None, BAND_UNKNOWN), ("nan", BAND_UNKNOWN),
])
def test_series_band(series, band):
    assert series_band(series) == band


def test_series_bb_is_not_series_b():
    """The trailing boundary in the shared regex -- 'Series BB' must not read as B."""
    assert series_band("Series BB") == BAND_ABOVE_B


# ── Oscar's rule ─────────────────────────────────────────────────────────────

def test_above_b_with_tier1_33_is_qualified():
    stage, tags, _ = expected_placement("Series D", [], TIER33)
    assert (stage, tags) == ("Qualified", [])


def test_above_b_without_tier1_33_is_unplaced():
    """The clause that makes this reconciler stricter than live intake."""
    stage, _, why = expected_placement("Series D", [], [])
    assert stage is None
    assert "no Tier 1 (33)" in why


def test_below_b_with_top10_is_radar():
    stage, tags, _ = expected_placement("Seed", TOP10, [])
    assert (stage, tags) == ("Radar", [])


def test_below_b_without_top10_is_unplaced():
    assert expected_placement("Seed", [], TIER33)[0] is None


def test_top10_implies_tier1_33():
    """TOP10 is a subset of the 33, so an above-B deal backed only by a Top 10
    firm still satisfies the Qualified clause even with tier1_33_firms empty."""
    assert expected_placement("Series C", TOP10, [])[0] == "Qualified"


def test_series_b_top10_dual_mode_is_qualified_plus_radar_tag():
    stage, tags, _ = expected_placement("Series B", TOP10, TIER33, series_b_mode="dual")
    assert (stage, tags) == ("Qualified", ["radar"])


def test_series_b_top10_radar_mode_is_radar_only():
    stage, tags, _ = expected_placement("Series B", TOP10, TIER33, series_b_mode="radar")
    assert (stage, tags) == ("Radar", [])


def test_series_b_without_top10_is_unplaced_in_both_modes():
    for mode in ("dual", "radar"):
        assert expected_placement("Series B", [], TIER33, series_b_mode=mode)[0] is None


def test_unknown_series_is_never_guessed():
    assert expected_placement("", TOP10, TIER33)[0] is None


# ── name normalization ───────────────────────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    ("Acme, Inc.", "Acme"), ("Acme Technologies", "acme"), ("Loop (Chicago)", "loop chicago"),
])
def test_norm_name_collapses_variants(a, b):
    assert ds.norm_name(a) == ds.norm_name(b)


def test_norm_name_keeps_distinct_companies_distinct():
    assert ds.norm_name("Console") != ds.norm_name("Consol")


# ── matching ─────────────────────────────────────────────────────────────────

def _hub(key, name, domain="", **kw):
    return {"key": key, "name": name, "domain": domain, "series": "", "stage": None,
            "tags": [], "investors": [], "investorDomains": [], "top10": [], "tier1_33": [],
            "attioRecordId": "", "attioStage": "", "originSource": "", **kw}


def _attio(key, name, domain="", **kw):
    return {"key": key, "name": name, "domain": domain, "series": "", "stage": "",
            "record_id": "", "investors": [], "investorDomains": [], "top10": [],
            "tier1_33": [], "rounds": [], "dealCount": 1, **kw}


def test_link_matches_on_key_first():
    matched, hub_only, attio_only = ds.link({"acme": _hub("acme", "Acme")},
                                            {"acme": _attio("acme", "Acme")})
    assert [b for _, _, b in matched] == ["key"]
    assert not hub_only and not attio_only


def test_link_falls_back_to_domain_then_name():
    """A hub doc keyed by name (no website when it was created) and its Attio
    deal keyed by domain would otherwise be two false 'missing' findings."""
    hub = {"acme-corp": _hub("acme-corp", "Acme Corp", domain="acme.com"),
           "widgetco": _hub("widgetco", "Widget Co, Inc.")}
    attio = {"acme": _attio("acme", "Acme", domain="acme.com"),
             "widget": _attio("widget", "Widget Co")}
    matched, hub_only, attio_only = ds.link(hub, attio)
    assert sorted(b for _, _, b in matched) == ["domain", "name"]
    assert not hub_only and not attio_only


def test_link_never_matches_one_hub_company_to_two_deals():
    hub = {"acme": _hub("acme", "Acme", domain="acme.com")}
    attio = {"acme": _attio("acme", "Acme", domain="acme.com"),
             "acme-two": _attio("acme-two", "Acme", domain="acme.com")}
    matched, hub_only, attio_only = ds.link(hub, attio)
    assert len(matched) == 1
    assert [r["key"] for r in attio_only] == ["acme-two"]


def test_link_reports_genuinely_one_sided_companies():
    matched, hub_only, attio_only = ds.link({"only-hub": _hub("only-hub", "Hub Only")},
                                            {"only-attio": _attio("only-attio", "Attio Only")})
    assert not matched
    assert [r["key"] for r in hub_only] == ["only-hub"]
    assert [r["key"] for r in attio_only] == ["only-attio"]


# ── hub snapshot folding ─────────────────────────────────────────────────────

def test_round_docs_fold_into_their_parent():
    """`${key}--${round}` docs are extra ROUNDS of a company already counted --
    left alone they'd each report as a separate hub-only company."""
    hub = ds.hub_companies_from_snapshot([
        {"id": "ollama", "name": "Ollama", "stage": "qualified"},
        {"id": "ollama--series-a", "companyKey": "ollama", "name": "Ollama", "round": "Series A"},
    ])
    assert list(hub) == ["ollama"]
    assert hub["ollama"]["extraRoundDocs"] == 1


def test_orphan_round_doc_still_appears():
    hub = ds.hub_companies_from_snapshot(
        [{"id": "ghost--series-b", "name": "Ghost", "round": "Series B"}])
    assert hub["ghost"]["originSource"] == "orphan-round-doc"


def test_cap_table_is_recomputed_not_trusted():
    """Stored top10Investors is exactly the field this report exists to catch
    drifting, so membership is derived from the investor list every run."""
    hub = ds.hub_companies_from_snapshot([{
        "id": "acme", "name": "Acme", "investors": ["Sequoia Capital"],
        "top10Investors": [], "tier1_33Investors": [],
    }])
    assert hub["acme"]["top10"] == ["Sequoia Capital"]


# ── reconcile ────────────────────────────────────────────────────────────────

def test_matched_companies_partition_across_the_five_buckets():
    """Every matched deal must land in exactly one bucket -- the guarantee the
    report's own arithmetic line makes to the reader."""
    hub = {
        "a": _hub("a", "A", stage="qualified"),
        "b": _hub("b", "B", stage="new"),
        "c": _hub("c", "C", stage="pipeline"),
        "d": _hub("d", "D", stage="watchlist"),
        "e": _hub("e", "E", stage="watchlist"),
    }
    attio = {
        "a": _attio("a", "A", series="Series C", stage="Qualified", investors=["Sequoia Capital"]),
        "b": _attio("b", "B", series="Series C", stage="Target", investors=["Sequoia Capital"]),
        "c": _attio("c", "C", series="Series C", stage="Passed", investors=["Sequoia Capital"]),
        "d": _attio("d", "D", series="Series D", stage="Watchlist", investors=["Nobody Capital"]),
        "e": _attio("e", "E", series="Seed", stage="Watchlist", investors=["Nobody Capital"]),
    }
    rep = ds.reconcile(hub, attio)
    c = rep["counts"]
    assert c["matched"] == 5
    assert (c["placementAgreed"] + c["placementMismatches"] + c["humanFiled"]
            + c["aboveBNoTier33"] + c["unplacedByRule"]) == c["matched"]
    assert c["placementAgreed"] == 1        # A: qualified both sides
    assert c["placementMismatches"] == 1    # B: hub 'new', Attio 'Target'
    assert c["humanFiled"] == 1             # C: Passed -- rule must not touch it
    assert c["aboveBNoTier33"] == 1         # D
    assert c["unplacedByRule"] == 1         # E


def test_passed_deals_are_never_proposed_for_a_move():
    hub = {"a": _hub("a", "A", stage="new")}
    attio = {"a": _attio("a", "A", series="Series C", stage="Passed",
                         investors=["Sequoia Capital"])}
    rep = ds.reconcile(hub, attio)
    assert rep["mismatches"] == []
    assert rep["humanFiled"][0]["name"] == "A"


def test_unplaced_hub_company_gets_a_stage_not_a_tag():
    hub = {"a": _hub("a", "A", stage="new")}
    attio = {"a": _attio("a", "A", series="Series C", stage="Qualified",
                         investors=["Sequoia Capital"])}
    m = ds.reconcile(hub, attio)["mismatches"][0]
    assert m["hubSetStage"] == "qualified"
    assert m["hubAddTags"] == []


def test_already_filed_hub_company_gets_a_tag_not_a_stage_rewrite():
    """A company someone put in Pipeline by hand keeps its stage; the extra tab
    membership arrives as an additive tag, which is how hub-next models it."""
    hub = {"a": _hub("a", "A", stage="pipeline")}
    attio = {"a": _attio("a", "A", series="Series C", stage="Qualified",
                         investors=["Sequoia Capital"])}
    m = ds.reconcile(hub, attio)["mismatches"][0]
    assert m["hubSetStage"] is None
    assert m["hubAddTags"] == ["qualified"]


def test_series_b_dual_case_wants_both_buckets():
    hub = {"a": _hub("a", "A", stage="new")}
    attio = {"a": _attio("a", "A", series="Series B", stage="Qualified",
                         investors=["Sequoia Capital"])}
    m = ds.reconcile(hub, attio)["mismatches"][0]
    assert m["hubSetStage"] == "qualified"
    assert m["hubAddTags"] == ["radar"]


def test_hub_membership_is_stage_union_tags():
    """Qualified-by-tag counts as being in the Qualified tab -- no false mismatch."""
    hub = {"a": _hub("a", "A", stage="pipeline", tags=["qualified"])}
    attio = {"a": _attio("a", "A", series="Series C", stage="Qualified",
                         investors=["Sequoia Capital"])}
    rep = ds.reconcile(hub, attio)
    assert rep["counts"]["placementAgreed"] == 1


def test_cap_table_is_unioned_across_both_sides():
    """Either side can be the one holding the investor list."""
    hub = {"a": _hub("a", "A", stage="qualified", investors=["Sequoia Capital"])}
    attio = {"a": _attio("a", "A", series="Series C", stage="Qualified")}
    rep = ds.reconcile(hub, attio)
    assert rep["counts"]["placementAgreed"] == 1
    assert rep["mismatches"] == []


def test_one_sided_rows_carry_their_expected_placement():
    rep = ds.reconcile({}, {"a": _attio("a", "A", series="Series C",
                                        investors=["Sequoia Capital"])})
    assert rep["attioOnly"][0]["expectedHubStage"] == "Qualified"


# ── Attio deal history (pipeline / passed / invested) ────────────────────────

def test_passed_always_brings_pipeline_with_it():
    assert sorted(ds.attio_stage_tags("Passed")) == ["passed", "pipeline"]


@pytest.mark.parametrize("stage,tags", [
    ("Pipeline", ["pipeline"]), ("Qualified", ["qualified"]),
    ("Invested", ["invested"]), ("Watchlist", ["watchlist"]), ("Radar", ["radar"]),
])
def test_attio_stage_maps_to_its_hub_bucket(stage, tags):
    assert ds.attio_stage_tags(stage) == tags


@pytest.mark.parametrize("stage", ["Target", "", None, "Some New Stage"])
def test_unmapped_attio_stage_yields_nothing_rather_than_a_guess(stage):
    assert ds.attio_stage_tags(stage) == []


def test_history_is_cumulative_across_every_deal_for_the_company():
    """A company passed on in May and re-opened as Qualified in June was still
    passed on. Reading only the latest deal dropped that."""
    hub = {"warp": _hub("warp", "Warp", stage="qualified")}
    attio = {"warp": _attio("warp", "Warp", series="Series B", stage="Qualified",
                            allStages=["Passed", "Qualified"])}
    rep = ds.reconcile(hub, attio)
    assert rep["historyGaps"][0]["historyMissing"] == ["passed", "pipeline"]


def test_history_is_recorded_for_passed_deals_the_rule_will_not_touch():
    """The terminal-stage branch skips placement, but history still applies --
    these are precisely the deals whose history matters most."""
    hub = {"a": _hub("a", "A", stage="qualified")}
    attio = {"a": _attio("a", "A", series="Series C", stage="Passed",
                         allStages=["Passed"], investors=["Sequoia Capital"])}
    rep = ds.reconcile(hub, attio)
    assert rep["counts"]["humanFiled"] == 1
    assert rep["historyGaps"][0]["historyMissing"] == ["passed", "pipeline"]


def test_no_history_gap_when_the_hub_already_carries_the_tags():
    hub = {"a": _hub("a", "A", stage="qualified", tags=["passed", "pipeline"])}
    attio = {"a": _attio("a", "A", series="Series C", stage="Passed",
                         allStages=["Passed"], investors=["Sequoia Capital"])}
    assert ds.reconcile(hub, attio)["counts"]["historyGaps"] == 0


def test_history_falls_back_to_the_single_stage_when_no_deal_list_is_present():
    hub = {"a": _hub("a", "A", stage="qualified")}
    attio = {"a": _attio("a", "A", series="Series C", stage="Pipeline")}
    assert ds.reconcile(hub, attio)["historyGaps"][0]["historyMissing"] == ["pipeline"]


# ── duplicate hub docs ───────────────────────────────────────────────────────

def _dup_snapshot():
    """The real shape: one doc keyed by domain (from the Attio import) and its
    twin keyed by the name slug (from a screening run that had no domain)."""
    return [
        {"id": "distyl", "name": "Distyl AI", "website": "distyl.ai", "stage": "qualified",
         "origin": {"source": "attio"}},
        {"id": "distyl-ai", "name": "Distyl AI",
         "latestScreen": {"fitScore": 3.6, "gate": True}},
    ]


def test_duplicate_docs_are_clustered_by_name():
    hub = ds.hub_companies_from_snapshot(_dup_snapshot())
    dupes = ds.find_hub_duplicates(hub)
    assert len(dupes) == 1
    assert dupes[0]["primaryKey"] == "distyl"
    assert [d["key"] for d in dupes[0]["duplicates"]] == ["distyl-ai"]


def test_duplicate_report_names_the_stranded_data():
    """The point of the section: the screen is on the twin, so the real company
    shows no fit score."""
    hub = ds.hub_companies_from_snapshot(_dup_snapshot())
    dup = ds.find_hub_duplicates(hub)[0]["duplicates"][0]
    assert "latestScreen" in dup["stranded"]
    assert dup["latestScreen"]["fitScore"] == 3.6


def test_the_doc_with_the_attio_origin_is_the_primary():
    """Order in the snapshot must not decide which doc is real."""
    hub = ds.hub_companies_from_snapshot(list(reversed(_dup_snapshot())))
    assert ds.find_hub_duplicates(hub)[0]["primaryKey"] == "distyl"


def test_docs_sharing_a_domain_cluster_even_with_different_names():
    hub = ds.hub_companies_from_snapshot([
        {"id": "launchfirestorm", "name": "Firestorm Labs", "website": "firestorm.com",
         "stage": "passed", "origin": {"source": "attio"}},
        {"id": "firestorm", "name": "Firestorm", "website": "firestorm.com"},
    ])
    assert len(ds.find_hub_duplicates(hub)) == 1


def test_distinct_companies_are_not_reported_as_duplicates():
    hub = ds.hub_companies_from_snapshot([
        {"id": "acme", "name": "Acme", "website": "acme.com"},
        {"id": "beta", "name": "Beta", "website": "beta.com"},
    ])
    assert ds.find_hub_duplicates(hub) == []


def test_duplicates_of_a_matched_company_leave_the_hub_only_list():
    """The bug this section fixes: the twin reported as 'missing from Attio'
    when Attio has the company perfectly well under the other doc."""
    hub = ds.hub_companies_from_snapshot(_dup_snapshot())
    attio = {"distyl": _attio("distyl", "Distyl AI", domain="distyl.ai", series="Series B")}
    rep = ds.reconcile(hub, attio)
    assert rep["counts"]["hubOnly"] == 0
    assert rep["counts"]["hubDuplicateDocs"] == 1


def test_a_duplicate_cluster_that_never_reached_attio_stays_hub_only():
    """Only a duplicate of a company that MATCHED is explained away -- otherwise
    a genuinely missing company would be hidden by having a twin."""
    hub = ds.hub_companies_from_snapshot([
        {"id": "ghost", "name": "Ghost", "website": "ghost.com", "stage": "pipeline"},
        {"id": "ghost-inc", "name": "Ghost Inc"},
    ])
    rep = ds.reconcile(hub, {})
    assert {r["key"] for r in rep["hubOnly"]} == {"ghost", "ghost-inc"}


def test_example_domain_fixtures_are_not_reported_as_missing_from_attio():
    hub = ds.hub_companies_from_snapshot(
        [{"id": "example-cascade", "name": "Cascade Analytics",
          "website": "cascadeanalytics.example", "stage": "pipeline"}])
    rep = ds.reconcile(hub, {})
    assert rep["counts"]["hubOnly"] == 0
    assert rep["counts"]["testFixtures"] == 1


# ── seeding companies that exist on neither side ─────────────────────────────

def test_read_seed_file_parses_a_csv_with_a_header(tmp_path):
    p = tmp_path / "seed.csv"
    p.write_text("name,domain,series,stage\nOneBrief,onebrief.com,Series C,Pipeline\n")
    assert ds.read_seed_file(str(p)) == [
        {"name": "OneBrief", "domain": "onebrief.com", "series": "Series C", "stage": "Pipeline"}]


def test_read_seed_file_accepts_a_bare_name_list(tmp_path):
    p = tmp_path / "seed.txt"
    p.write_text("OneBrief\nReplit\n")
    rows = ds.read_seed_file(str(p))
    assert [r["name"] for r in rows] == ["OneBrief", "Replit"]
    assert all(r["stage"] == ds.DEFAULT_SEED_STAGE for r in rows)


def test_seed_reports_a_company_missing_from_both_sides():
    seed = ds.check_seed([{"name": "OneBrief", "domain": "onebrief.com",
                           "series": "", "stage": "Pipeline"}], {}, {})
    assert (seed[0]["inAttio"], seed[0]["inHub"]) == (False, False)


def test_seed_matches_an_existing_company_under_a_different_name():
    """Warp is 'Warp (Business/Productivity Software)' in Attio -- seeding it
    must report it as present, not create a duplicate."""
    attio = {"warp": _attio("warp", "Warp (Business/Productivity Software)",
                            domain="warp.co", stage="Qualified")}
    seed = ds.check_seed([{"name": "Warp", "domain": "warp.dev",
                           "series": "", "stage": "Pipeline"}], {}, attio)
    assert seed[0]["inAttio"] is True
    assert seed[0]["matchedName"] == "Warp (Business/Productivity Software)"


def test_attio_import_csv_holds_only_what_attio_lacks(tmp_path):
    seed = [{"name": "New Co", "domain": "new.com", "series": "Series C",
             "stage": "Pipeline", "inAttio": False},
            {"name": "Old Co", "domain": "old.com", "series": "", "stage": "Pipeline",
             "inAttio": True}]
    path, n = ds.write_attio_import_csv(seed, str(tmp_path / "import.csv"))
    assert n == 1
    body = open(path).read()
    assert "New Co" in body and "Old Co" not in body


def test_seed_flags_a_company_id8_already_owns():
    """Default seed stage is Pipeline, so a holding would be filed as a prospect."""
    seed = ds.check_seed([{"name": "Replit", "domain": "replit.com",
                           "series": "", "stage": "Pipeline"}], {}, {})
    assert seed[0]["isHolding"] is True


def test_seed_does_not_flag_an_ordinary_company():
    seed = ds.check_seed([{"name": "OneBrief", "domain": "onebrief.com",
                           "series": "", "stage": "Pipeline"}], {}, {})
    assert seed[0]["isHolding"] is False


def test_holding_warning_is_silent_once_the_stage_is_invested(capsys):
    """A warning that fires on the correct case is one nobody reads on the
    incorrect case."""
    report = {"hubOnly": [], "seed": [{"name": "Replit", "domain": "replit.com",
                                       "series": "", "stage": "Invested",
                                       "inAttio": False, "isHolding": True}]}
    ds.apply_attio(report, yes=False)
    assert "ID8 HOLDING" not in capsys.readouterr().out


def test_holding_warning_fires_when_the_stage_is_wrong(capsys):
    report = {"hubOnly": [], "seed": [{"name": "Replit", "domain": "replit.com",
                                       "series": "", "stage": "Pipeline",
                                       "inAttio": False, "isHolding": True}]}
    ds.apply_attio(report, yes=False)
    assert "ID8 HOLDING" in capsys.readouterr().out


def test_apply_attio_dry_run_needs_no_credentials(monkeypatch):
    """A preview makes no API calls, so requiring a key to see the plan locked
    the one machine without one out of ever reviewing it."""
    monkeypatch.setattr(ds.config, "ATTIO_API_KEY", None)
    report = {"hubOnly": [], "seed": [{"name": "OneBrief", "domain": "onebrief.com",
                                       "series": "", "stage": "Pipeline", "inAttio": False}]}
    assert ds.apply_attio(report, yes=False) == {"created": 0, "dryRun": True}


# ── the names list ───────────────────────────────────────────────────────────

def test_check_names_reports_each_side_independently():
    hub = {"a": _hub("a", "Acme, Inc.", stage="qualified")}
    attio = {"b": _attio("b", "Beta", series="Series C")}
    rows = ds.check_names(["Acme", "Beta", "Gamma"], hub, attio)
    assert [(r["inHub"], r["inAttio"]) for r in rows] == [(True, False), (False, True), (False, False)]


def test_read_names_file_skips_blanks_and_comments(tmp_path):
    p = tmp_path / "names.txt"
    p.write_text("# my list\n\nAcme\n\"Beta, Inc.\"\nGamma\n")
    assert ds.read_names_file(str(p)) == ["Acme", "Beta, Inc.", "Gamma"]
