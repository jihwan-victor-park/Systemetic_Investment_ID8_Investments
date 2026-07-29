"""Unit tests for radar_access.py's pure syndicate/access resolution --
fabricated inputs, zero mocking (build_partner_index takes an already-
fetched list, same convention as radar_mandate.build_tier1_index)."""
from deal_intelligence import radar_access as ra

PARTNER_VCS = [
    {"name": "Acme Ventures", "portfolio": [{"company": "Northwind Systems"}, {"company": "Halden Compute"}]},
    {"name": "Beacon Capital", "portfolio": [{"company": "Northwind Systems"}]},  # dupe company, different firm -- both should show up
]


def test_build_partner_index_shape():
    index = ra.build_partner_index(PARTNER_VCS)
    assert set(index["northwind systems"]) == {"Acme Ventures", "Beacon Capital"}
    assert index["halden compute"] == ["Acme Ventures"]


def test_build_partner_index_empty_input():
    assert ra.build_partner_index([]) == {}
    assert ra.build_partner_index(None) == {}


def test_build_partner_index_skips_firm_with_no_name():
    index = ra.build_partner_index([{"portfolio": [{"company": "Ghost Co"}]}])
    assert index == {}


def test_build_partner_index_dedupes_same_company_twice_under_one_firm():
    index = ra.build_partner_index([{"name": "Acme Ventures", "portfolio": [{"company": "Dup Co"}, {"company": "Dup Co"}]}])
    assert index["dup co"] == ["Acme Ventures"]


def test_resolve_access_co_invest_is_the_top_tier():
    index = ra.build_partner_index(PARTNER_VCS)
    result = ra.resolve_access("Northwind Systems", tier1_firms=["Sequoia"], top10_vc_flag=True, partner_index=index)
    assert result["level"] == "co-invest"
    assert result["accessPass"] is True
    assert set(result["coInvestFirms"]) == {"Acme Ventures", "Beacon Capital"}


def test_resolve_access_institutional_when_no_partner_match_but_tier1_present():
    result = ra.resolve_access("Some Co", tier1_firms=["Sequoia"], top10_vc_flag=False, partner_index={})
    assert result["level"] == "institutional"
    assert result["accessPass"] is True
    assert result["coInvestFirms"] == []


def test_resolve_access_institutional_via_top10_flag_alone():
    result = ra.resolve_access("Some Co", tier1_firms=[], top10_vc_flag=True, partner_index={})
    assert result["level"] == "institutional"
    assert result["accessPass"] is True


def test_resolve_access_none_when_neither():
    result = ra.resolve_access("Unknown Co", tier1_firms=[], top10_vc_flag=False, partner_index={})
    assert result["level"] == "none"
    assert result["accessPass"] is False


def test_resolve_access_case_insensitive_name_match():
    index = ra.build_partner_index(PARTNER_VCS)
    result = ra.resolve_access("northwind SYSTEMS", tier1_firms=[], top10_vc_flag=False, partner_index=index)
    assert result["level"] == "co-invest"


def test_resolve_access_no_company_name_never_crashes():
    result = ra.resolve_access(None, tier1_firms=[], top10_vc_flag=False, partner_index={})
    assert result["level"] == "none"
