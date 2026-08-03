"""Covers the Tier 1 / Top 10 registry and its cap-table matching.

The point of this module is to be strictly MORE precise than Attio's "Top 10
VC" saved search, which matches `Investors > Name contains <word>` and
therefore over-matches on several of these firms. The false-positive cases
below (Bain & Company, Bessemer Trust, Accel-KKR, bare "Index") are the
specific reasons the code exists -- each one would be a wrong Top 10 VC flag
in the CRM today, and a wrong flag feeds routing and the mandate screen.
"""
from deal_intelligence import tier1_firms as t1


# ── domain matching (the precise signal) ──────────────────────────────────────

def test_matches_by_domain():
    assert t1.match_top10(investor_domains=["sequoiacap.com"]) == ["Sequoia Capital"]
    assert t1.match_top10(investor_domains=["bvp.com"]) == ["Bessemer Venture Partners"]


def test_domain_matching_tolerates_urls_and_www_and_paths():
    for raw in ("https://www.sequoiacap.com", "www.sequoiacap.com",
                "SEQUOIACAP.COM", "https://sequoiacap.com/team/"):
        assert t1.match_top10(investor_domains=[raw]) == ["Sequoia Capital"], raw


def test_unknown_domain_matches_nothing():
    assert t1.match_top10(investor_domains=["some-random-seed-fund.com"]) == []


# ── name matching (parallel to domains, not a fallback) ───────────────────────

def test_matches_by_name():
    assert t1.match_top10(investor_names=["Sequoia Capital"]) == ["Sequoia Capital"]
    assert t1.match_top10(investor_names=["Index Ventures"]) == ["Index Ventures"]
    assert t1.match_top10(investor_names=["ICONIQ Growth"]) == ["ICONIQ Capital"]


def test_name_matching_survives_pitchbook_name_noise():
    # PitchBook glues on parentheticals and regional suffixes.
    assert t1.match_top10(investor_names=["Sequoia Capital (US)"]) == ["Sequoia Capital"]
    assert t1.match_top10(investor_names=["Sequoia Capital China"]) == ["Sequoia Capital"]
    assert t1.match_top10(investor_names=["Accel Partners"]) == ["Accel"]


def test_a_name_hit_still_works_when_the_domain_is_absent_or_wrong():
    """Domains here are well-known values, not verified against a live export,
    so a domain miss must never cause a false negative."""
    assert t1.match_top10(
        investor_domains=["not-the-real-sequoia-domain.com"],
        investor_names=["Sequoia Capital"],
    ) == ["Sequoia Capital"]


# ── the false positives Attio's `contains` filter produces ────────────────────

def test_bain_and_company_is_not_bain_capital_ventures():
    assert t1.match_top10(investor_names=["Bain & Company"]) == []
    assert t1.match_top10(investor_names=["Bain and Company"]) == []
    # ...but the real venture/growth arm does match.
    assert t1.match_top10(investor_names=["Bain Capital Ventures"]) == ["Bain Capital Ventures"]
    assert t1.match_top10(investor_names=["Bain Capital"]) == ["Bain Capital Ventures"]


def test_bessemer_trust_is_not_bessemer_venture_partners():
    assert t1.match_top10(investor_names=["Bessemer Trust"]) == []
    assert t1.match_top10(investor_names=["Bessemer Venture Partners"]) == ["Bessemer Venture Partners"]


def test_accel_kkr_is_not_accel():
    assert t1.match_top10(investor_names=["Accel-KKR"]) == []
    assert t1.match_top10(investor_names=["Accel KKR"]) == []
    assert t1.match_top10(investor_names=["Accel"]) == ["Accel"]


def test_bare_index_does_not_match_index_ventures():
    # 'contains Index' in Attio matches anything with the substring; here only
    # the real firm name does.
    assert t1.match_top10(investor_names=["Index"]) == []
    assert t1.match_top10(investor_names=["S&P Dow Jones Indices"]) == []
    assert t1.match_top10(investor_names=["Index Ventures"]) == ["Index Ventures"]


def test_bare_generic_words_do_not_match():
    for name in ["Benchmark Electronics", "Thrive Market", "Lightspeed Commerce",
                 "Sequoia Financial Group"]:
        assert t1.match_top10(investor_names=[name]) == [], name


def test_substring_inside_a_word_never_matches():
    assert t1.match_top10(investor_names=["Reindex Ventures Fund"]) == []
    assert t1.match_top10(investor_names=["Accelerate Partners"]) == []


# ── output shape ──────────────────────────────────────────────────────────────

def test_dedupes_across_domain_and_name_hits():
    assert t1.match_top10(
        investor_domains=["sequoiacap.com"], investor_names=["Sequoia Capital"],
    ) == ["Sequoia Capital"]


def test_output_is_stable_in_registry_order_not_input_order():
    a = t1.match_top10(investor_names=["Bessemer Venture Partners", "Sequoia Capital"])
    b = t1.match_top10(investor_names=["Sequoia Capital", "Bessemer Venture Partners"])
    assert a == b
    assert a.index("Sequoia Capital") < a.index("Bessemer Venture Partners")


def test_empty_and_none_inputs_are_safe():
    assert t1.match_top10() == []
    assert t1.match_top10(investor_domains=None, investor_names=None) == []
    assert t1.match_top10(investor_domains=[], investor_names=[""]) == []
    assert t1.match_top10(investor_names=[None]) == []


def test_is_top10_backed():
    assert t1.is_top10_backed(investor_names=["Thrive Capital"]) is True
    assert t1.is_top10_backed(investor_names=["Bain & Company"]) is False


def test_all_ten_firms_resolve_from_oscars_attio_filter_words():
    """The ten words in Oscar's Attio saved-search screenshot, each resolving to
    exactly one canonical firm (using the qualifier where the bare word is too
    generic to accept -- see the registry's alias comments)."""
    cases = {
        "Sequoia Capital": "Sequoia Capital",
        "Index Ventures": "Index Ventures",
        "Iconiq Growth": "ICONIQ Capital",
        "Benchmark Capital": "Benchmark",
        "Accel": "Accel",
        "Thrive Capital": "Thrive Capital",
        "Lightspeed Venture Partners": "Lightspeed Venture Partners",
        "Bain Capital Ventures": "Bain Capital Ventures",
        "Greenoaks Capital Partners": "Greenoaks Capital Partners",
        "Bessemer Venture Partners": "Bessemer Venture Partners",
    }
    for raw, expected in cases.items():
        assert t1.match_top10(investor_names=[raw]) == [expected], raw
    assert len(t1.TOP10_NAMES) == 10


# ── the broader 33 ────────────────────────────────────────────────────────────

def test_tier1_33_exact_name_match():
    assert t1.match_tier1_33(["Khosla Ventures"]) == ["Khosla Ventures"]
    assert t1.match_tier1_33(["Andreessen Horowitz"]) == ["Andreessen Horowitz"]
    assert t1.match_tier1_33(["Some Random Fund"]) == []


def test_top10_is_a_subset_of_the_33():
    """TIER1_33 uses PitchBook's fuller legal names for a few firms, so compare
    on the normalized key rather than the canonical display name."""
    keys_33 = {t1.normalize_firm_name(f) for f in t1.TIER1_33}
    for firm in t1.TOP10:
        assert any(t1.normalize_firm_name(a) in keys_33 or
                   any(t1.normalize_firm_name(a) in k for k in keys_33)
                   for a in firm["aliases"]), firm["name"]
