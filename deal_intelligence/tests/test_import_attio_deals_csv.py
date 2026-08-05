"""Unit tests for import_attio_deals_csv.py's pure functions -- fabricated
row dicts, no CSV file or Firestore I/O, same convention as
test_radar_hazard.py/test_capital_clock.py."""
from deal_intelligence import import_attio_deals_csv as m


def _row(name="Acme", domain="acme.com", stage="Pipeline", deal_date="2026-01-01",
         stage_changed_at="2026-01-01T00:00:00Z", series="Series B", description="",
         investor_names=None, investor_domains=None):
    return {
        "name": name, "domain": domain, "stage": stage, "deal_date": deal_date,
        "stage_changed_at": stage_changed_at, "series": series, "description": description,
        "investor_names": investor_names or [], "investor_domains": investor_domains or [],
    }


# ── company_key_of ──────────────────────────────────────────────────────

def test_company_key_prefers_domain():
    assert m.company_key_of("https://www.acme.com/", "Acme Corp") == "acme"


def test_company_key_falls_back_to_name_when_no_domain():
    assert m.company_key_of("", "Acme (Business/Productivity Software)") == "acme-business-productivity-software"


def test_company_key_same_domain_different_names_match():
    # The real "MicroOne"/"Micro1" case from the actual export -- same
    # company, name drifted between records, domain is the stable anchor.
    assert m.company_key_of("micro1.ai", "MicroOne") == m.company_key_of("micro1.ai", "Micro1")


# ── parse_comma_list (investor names AND investor domains) ─────────────

def test_parse_comma_list_splits_and_dedupes():
    assert m.parse_comma_list("Sequoia Capital,Index Ventures,Sequoia Capital") == ["Index Ventures", "Sequoia Capital"]


def test_parse_comma_list_empty_cell_is_empty_list():
    assert m.parse_comma_list("") == []
    assert m.parse_comma_list(None) == []


def test_parse_comma_list_handles_embedded_comma_in_a_quoted_name():
    # Real edge case from the actual export: a firm name itself contains a
    # comma, quoted by Attio's own CSV export -- must parse as ONE name
    # plus the two real ones, not four fragments.
    result = m.parse_comma_list('"Atreides Management,",Index Ventures,TCV')
    assert len(result) == 3
    assert "Index Ventures" in result
    assert "TCV" in result


def test_parse_comma_list_works_for_domains_too():
    # Same parser feeds 'Investors > Domains' (CSV (12)'s new column) --
    # positionally correlated with 'Investors > Name' in the export, but
    # match_top10 matches domains and names independently (OR'd), so no
    # positional alignment is needed here.
    assert m.parse_comma_list("thrivecap.com,dst-global.com,svangel.com") == ["dst-global.com", "svangel.com", "thrivecap.com"]


# ── read_rows carries investor_domains ──────────────────────────────────

def test_read_rows_defaults_investor_domains_to_empty_list_when_column_absent(tmp_path):
    # The original CSV (11) shape -- no 'Investors > Domains' column at all.
    csv_path = tmp_path / "deals.csv"
    csv_path.write_text("Record,Associated company > Domains,Deal stage,Deal Date,Series\nAcme,acme.com,Pipeline,2026-01-01,Series B\n")
    rows = list(m.read_rows(str(csv_path)))
    assert rows[0]["investor_domains"] == []


# ── group_by_company ─────────────────────────────────────────────────────

def test_group_by_company_groups_same_domain_together():
    rows = [_row(name="Ollama", domain="ollama.com"), _row(name="Ollama", domain="ollama.com", series="Series A")]
    groups = m.group_by_company(rows)
    assert len(groups) == 1
    assert len(next(iter(groups.values()))) == 2


def test_group_by_company_different_companies_stay_separate():
    rows = [_row(name="Ollama", domain="ollama.com"), _row(name="Ramp", domain="ramp.com")]
    groups = m.group_by_company(rows)
    assert len(groups) == 2


# ── authoritative_row ────────────────────────────────────────────────────

def test_authoritative_row_picks_latest_deal_date():
    older = _row(stage="Passed", deal_date="2026-05-18")
    newer = _row(stage="Qualified", deal_date="2026-06-25")
    assert m.authoritative_row([older, newer]) is newer


def test_authoritative_row_a_passed_company_that_later_requalified_is_not_passed():
    # The real Warp case from the actual export: an earlier round was
    # Passed, a LATER round is Qualified -- current state must read
    # Qualified, not Passed.
    passed_round = _row(name="Warp", stage="Passed", deal_date="2026-05-18")
    qualified_round = _row(name="Warp", stage="Qualified", deal_date="2026-06-25")
    auth = m.authoritative_row([passed_round, qualified_round])
    assert auth["stage"] == "Qualified"
    assert auth["stage"].strip().lower() != m.PASSED_STAGE


def test_authoritative_row_falls_back_to_stage_changed_at_when_deal_date_missing():
    missing_date = _row(deal_date="", stage_changed_at="2026-01-01T00:00:00Z", series="Series A")
    has_date = _row(deal_date="2026-02-01", stage_changed_at="2026-02-01T00:00:00Z", series="Series B")
    assert m.authoritative_row([missing_date, has_date]) is has_date


# ── _round_slug ───────────────────────────────────────────────────────────

def test_round_slug_from_series():
    assert m._round_slug("Series B") == "series-b"


def test_round_slug_defaults_when_no_series():
    assert m._round_slug("") == "round"
    assert m._round_slug(None) == "round"
