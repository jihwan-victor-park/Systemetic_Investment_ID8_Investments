"""Canonical Tier 1 / Top 10 VC firm registry, and cap-table matching against it.

Two distinct concepts, deliberately kept separate here because the codebase
already relies on both:

- **TOP10** -- the ten elite firms whose deals ID8 tracks at ANY stage. This is
  the set behind Attio's "Top 10 VC" saved search, the `top10VC` flag, and the
  /process-top10 intake pathway. Oscar's confirmed list, 2026-08-03.
- **TIER1_33** -- the broader 33-firm Tier 1 universe the weekly PitchBook
  deal-flow export is already filtered to (Series B+ from these firms). Lives in
  `pipeline/transform_pitchbook.py` as TIER1_FIRMS; mirrored here so both the
  Attio-side pipeline and deal_intelligence read one definition. TOP10 is a
  subset of it.

WHY THIS MODULE EXISTS (2026-08-03). Tier 1 presence on a cap table used to be
answered by name-matching a company against `topVCs[].deals[]` -- a per-firm,
hand-typed portfolio list in Firestore (see radar_mandate.build_tier1_index).
Oscar's call: stop maintaining portfolios entirely, and instead read Tier 1
presence off the investor DOMAINS that already arrive with every deal. Those
domains are real and already plumbed end-to-end:

    PitchBook export "Investors Websites" column
      -> pipeline/app.py parse_investor_websites() / resolve_investor_links()
      -> linked Attio Companies records on the deal's investor reference fields
      -> attio_io._investor_domains() reads them back
      -> firestore_push writes them to company.investorDomains

so no new data collection is needed -- only this matcher.

DOMAINS *AND* NAMES, OR'd. Domain matching is the precise signal, but the
domains below are well-known values, NOT verified against a live PitchBook
export (the repo's exports are investor-portfolio shaped and carry no
"Investors Websites" column to check against). So a domain miss must never
cause a false negative: name aliases are matched in parallel, and either hit
counts. Correct a domain here the moment a real export disagrees.

EXCLUSIONS ARE THE POINT. Attio's saved search matches `Investors > Name
contains <word>`, which over-matches badly on this particular list -- "Bain"
also catches Bain & Company (consulting), "Bessemer" also catches Bessemer
Trust (wealth management), "Accel" also catches Accel-KKR (a different, PE
firm), and "Index" catches anything containing the substring. Each firm below
carries an `exclude` list of normalized names that must NOT be treated as that
firm, so this matcher is strictly more precise than the CRM filter it backs.
"""
import re
import unicodedata

_LEGAL_SUFFIXES = {
    "inc", "incorporated", "llc", "llp", "ltd", "limited", "lp",
    "corp", "corporation", "plc", "gmbh", "ag", "sa",
}


def normalize_firm_name(name) -> str:
    """Loose match key for a firm name -- mirrors pipeline/app.py's
    normalize_company_name (accent folding, parenthetical/punctuation
    stripping, legal-suffix and leading-'the' removal) so a name normalized
    on either side of the pipeline produces the same key. Duplicated rather
    than imported because pipeline/app.py is a Flask app module that pulls in
    pandas/openpyxl/Attio config at import time; deal_intelligence must stay
    importable without any of that."""
    if not name:
        return ""
    s = str(name).lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"\([^)]*\)", " ", s)
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    tokens = [t for t in s.split() if t and t not in _LEGAL_SUFFIXES]
    if tokens and tokens[0] == "the":
        tokens = tokens[1:]
    return " ".join(tokens)


def normalize_domain(domain) -> str:
    """Bare host, lowercased: 'https://www.sequoiacap.com/team/' -> 'sequoiacap.com'."""
    if not domain:
        return ""
    d = re.sub(r"^https?://", "", str(domain).strip(), flags=re.IGNORECASE)
    d = d.replace("www.", "").strip().strip("/").lower()
    return d.split("/")[0]


# ── The Top 10 ────────────────────────────────────────────────────────────────
# `name` is canonical (what gets reported/stored). `aliases` are normalized
# name fragments that identify the firm; `exclude` are normalized names that
# contain an alias but are a DIFFERENT organization (see module docstring).
#
# Alias specificity is tuned per firm, not uniform: a distinctive coined word
# ("iconiq", "greenoaks") is safe on its own, while a common English word is
# only accepted with its qualifier ("index ventures", never bare "index";
# "benchmark capital", never bare "benchmark"; "thrive capital", never bare
# "thrive"). That asymmetry is deliberate -- it's exactly where the CRM's
# substring filter produces garbage.
TOP10 = [
    {
        "name": "Sequoia Capital",
        "domains": ["sequoiacap.com", "sequoia.com"],
        "aliases": ["sequoia capital", "sequoia"],
        # Unrelated firms that merely share the word.
        "exclude": ["sequoia financial group", "sequoia financial",
                    "sequoia investment management", "sequoia holdings"],
    },
    {
        "name": "Index Ventures",
        "domains": ["indexventures.com"],
        # Never bare "index" -- far too generic as a substring.
        "aliases": ["index ventures"],
        "exclude": [],
    },
    {
        "name": "ICONIQ Capital",
        "domains": ["iconiqcapital.com"],
        # Coined word; also covers the "ICONIQ Growth" branding PitchBook uses.
        "aliases": ["iconiq"],
        "exclude": [],
    },
    {
        "name": "Benchmark",
        "domains": ["benchmark.com", "benchmarkcapital.com"],
        # Never bare "benchmark" -- common noun, and PitchBook records the firm
        # as "Benchmark Capital Holdings".
        "aliases": ["benchmark capital", "benchmark holdings"],
        "exclude": ["benchmark electronics", "benchmark international"],
    },
    {
        "name": "Accel",
        "domains": ["accel.com", "accel.eu", "accelpartners.com"],
        "aliases": ["accel", "accel partners"],
        # Accel-KKR is a separate PE firm, not Accel.
        "exclude": ["accel kkr", "accelkkr"],
    },
    {
        "name": "Thrive Capital",
        "domains": ["thrivecap.com"],
        # Never bare "thrive".
        "aliases": ["thrive capital"],
        "exclude": ["thrive market", "thrive global"],
    },
    {
        "name": "Lightspeed Venture Partners",
        "domains": ["lsvp.com", "lightspeedvp.com"],
        "aliases": ["lightspeed venture", "lightspeed ventures", "lightspeed"],
        # Lightspeed Commerce is a public retail-software company.
        "exclude": ["lightspeed commerce", "lightspeed pos"],
    },
    {
        "name": "Bain Capital Ventures",
        "domains": ["baincapitalventures.com", "bcv.vc", "baincapital.com"],
        # Oscar's Attio filter is a broad "contains Bain", intending Bain
        # Capital's venture/growth arms -- kept broad here to match that
        # intent, minus the consultancy below.
        "aliases": ["bain capital ventures", "bain capital"],
        "exclude": ["bain and company", "bain company"],
    },
    {
        "name": "Greenoaks Capital Partners",
        "domains": ["greenoaks.com", "greenoakscap.com"],
        "aliases": ["greenoaks"],
        "exclude": [],
    },
    {
        "name": "Bessemer Venture Partners",
        "domains": ["bvp.com", "bessemervp.com"],
        "aliases": ["bessemer venture", "bessemer ventures", "bessemer"],
        # Bessemer Trust is an unrelated wealth manager.
        "exclude": ["bessemer trust", "bessemer group"],
    },
]

TOP10_NAMES = [f["name"] for f in TOP10]

# ── The broader Tier 1 universe (33 firms) ────────────────────────────────────
# The weekly PitchBook deal-flow export is already filtered to Series B+ deals
# from these firms, so a weekly-sourced deal is Tier 1-backed by construction.
# Mirrors pipeline/transform_pitchbook.py's TIER1_FIRMS. Names only -- domain
# precision matters most for the Top 10 (they drive routing and the top10VC
# flag); the rest are used for counting/context.
TIER1_33 = [
    "Sequoia Capital", "General Catalyst", "Accel", "Khosla Ventures",
    "Founders Fund", "Benchmark Capital Holdings", "Index Ventures",
    "Thrive Capital", "ICONIQ Capital", "Union Square Ventures",
    "Bessemer Venture Partners", "Lightspeed Venture Partners",
    "Bain Capital Ventures", "Andreessen Horowitz", "Kleiner Perkins",
    "Insight Partners", "IVP", "TCV", "Ribbit Capital", "Notable Capital",
    "New Enterprise Associates", "Dragoneer Investment Group",
    "Battery Ventures", "Valor Equity Partners", "Addition", "BOND Capital",
    "Oak HC/FT", "Coatue Management", "Lux Capital", "8VC", "Menlo Ventures",
    "Greenoaks Capital Partners", "DST Global",
]

# Normalized-name -> canonical name, for the 33. Built once at import.
_TIER1_33_BY_KEY = {normalize_firm_name(f): f for f in TIER1_33}

# Reverse lookups for the Top 10, built once at import.
_TOP10_BY_DOMAIN = {}
for _firm in TOP10:
    for _d in _firm["domains"]:
        _TOP10_BY_DOMAIN[normalize_domain(_d)] = _firm["name"]

_TOP10_ALIASES = [
    (normalize_firm_name(_a), _firm["name"], [normalize_firm_name(x) for x in _firm["exclude"]])
    for _firm in TOP10
    for _a in _firm["aliases"]
]
# Longest alias first, so "bain capital ventures" is tested before "bain
# capital" and the more specific match wins.
_TOP10_ALIASES.sort(key=lambda t: -len(t[0]))


def _name_matches_top10(raw_name) -> str | None:
    """Canonical Top 10 firm name for one investor name, or None.

    An alias hits when it appears as a whole-word run inside the normalized
    investor name -- so "sequoia capital china" matches "sequoia capital",
    while "sequoiah" or "reindex ventures" match nothing. Exclusions are
    checked first and win outright."""
    key = normalize_firm_name(raw_name)
    if not key:
        return None
    for alias, canonical, excludes in _TOP10_ALIASES:
        if not alias:
            continue
        if not re.search(rf"(?:^|\s){re.escape(alias)}(?:\s|$)", key):
            continue
        # A name that IS one of the known look-alikes is never this firm.
        if any(ex and re.search(rf"(?:^|\s){re.escape(ex)}(?:\s|$)", key) for ex in excludes):
            continue
        return canonical
    return None


def match_top10(investor_domains=None, investor_names=None) -> list:
    """Which Top 10 firms are on this cap table.

    investor_domains: domains of the deal's linked investor Companies records
    (DealInput.investor_domains / company.investorDomains). The precise signal.
    investor_names: raw investor name strings -- PitchBook's
    Lead/Sole Investors, New Investors, and Investors columns, or Attio's text
    equivalents. Matched in parallel, not as a fallback, so a domain we have
    wrong or missing still resolves by name (see module docstring).

    Returns canonical firm names, deduped, in TOP10 order (stable output for
    storage/diffing, rather than whatever order the inputs happened to be in).
    """
    hits = set()
    for d in investor_domains or []:
        canonical = _TOP10_BY_DOMAIN.get(normalize_domain(d))
        if canonical:
            hits.add(canonical)
    for n in investor_names or []:
        canonical = _name_matches_top10(n)
        if canonical:
            hits.add(canonical)
    return [f for f in TOP10_NAMES if f in hits]


def match_tier1_33(investor_names=None) -> list:
    """Which of the broader 33 Tier 1 firms are named on this cap table.
    Exact normalized-name match only -- this set is used for counting and
    context (radar_market_heat.tier1_investor_count), not for gating, so it
    stays deliberately stricter and simpler than match_top10's alias logic.
    Top 10 hits are folded in, since TOP10 is a subset of the 33 and its
    matcher is the more capable one."""
    hits = set()
    for n in investor_names or []:
        canonical = _TIER1_33_BY_KEY.get(normalize_firm_name(n))
        if canonical:
            hits.add(canonical)
    return sorted(hits)


def is_top10_backed(investor_domains=None, investor_names=None) -> bool:
    """True when any Top 10 firm is on the cap table. This is the code-side
    equivalent of Attio's "Top 10 VC" saved search, and is what the
    `top10VC` flag should reflect."""
    return bool(match_top10(investor_domains, investor_names))
