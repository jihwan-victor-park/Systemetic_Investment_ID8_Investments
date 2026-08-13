"""Reconciles the Attio Deals pipeline against the hub's Firestore companies --
what's on one side and missing from the other, and where the two disagree about
placement (Oscar, 2026-08-13: "a list of the deals which are in attio and not in
the hub and viceversa, so that we sync them up").

Read-only by default. It writes a report; it does not touch Attio or Firestore
unless you explicitly ask it to (see --apply-hub / --apply-attio, both dry-run
until --yes).

    # the usual run -- two files in, a report out, no credentials needed
    python3 -m deal_intelligence.deal_sync \
        --attio-csv deal_intelligence/data/attio-deals-export.csv \
        --hub-snapshot deal_intelligence/data/companies-snapshot.json

    # pull both sides live first (needs ATTIO_API_KEY + Firestore creds, i.e. Cloud Shell)
    python3 -m deal_intelligence.deal_sync --refresh

Where the two snapshots come from:
  - hub:   `python3 -m deal_intelligence.export_companies_snapshot` (Cloud Shell;
           dumps the whole `companies` collection), or --refresh here.
  - Attio: the Deals CSV export from Attio's own UI -- the same shape
           import_attio_deals_csv.py already parses, and the richest source
           available (it carries investor names AND domains, which the API path
           can only get with one extra GET per linked investor). --refresh pulls
           the equivalent over the API instead.

MATCHING. Both sides are keyed by `import_attio_deals_csv.company_key_of` --
domain-first slug, name slug as fallback -- which is the same id
`fit_note.company_id` gives a hub doc, so a company that came into the hub
through the normal Attio path lands on the identical key here. Two extra passes
catch the rest: normalized website domain, then normalized name. Without those,
a hub doc created by name (no website on file) and its Attio deal (which has a
domain) would each report as "missing on the other side" -- two false findings
per company, on the exact companies most likely to be genuinely half-synced.

PLACEMENT. `placement.expected_placement` holds Oscar's rule (Tier 1 (33) +
above B -> Qualified; Top 10 + B-or-below -> Radar). It is deliberately stricter
than the `determine_placement` the live intake path uses -- see that module's
own comment for why the two are kept apart rather than merged.

Multi-round companies (an Attio deal per round -- this export has several) are
grouped to one company on both sides, exactly as import_attio_deals_csv does:
the authoritative row is the latest by Deal Date, and the cap table is the union
across every round, since a Top 10 firm that came in at Series A is still on the
cap table at Series C.
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

from . import config, tier1_firms
from .fit_note import normalize_domain, slugify
from .import_attio_deals_csv import (PASSED_STAGE, PASSED_TAG, authoritative_row,
                                     company_key_of, group_by_company, read_rows)
from .placement import (BAND_ABOVE_B, BAND_B, BAND_BELOW_B, BAND_UNKNOWN,
                        expected_placement, series_band)

DEFAULT_ATTIO_CSV = "deal_intelligence/data/attio-deals-export.csv"
DEFAULT_HUB_SNAPSHOT = "deal_intelligence/data/companies-snapshot.json"
DEFAULT_ATTIO_SNAPSHOT = "deal_intelligence/data/attio-deals-snapshot.json"
DEFAULT_OUT_DIR = "deal_intelligence/data/sync"

# Attio deal stages that are a HUMAN filing decision, not something the series
# rule can second-guess. A deal Oscar personally passed on, or one already
# invested, must never show up as "should be Qualified" -- the rule doesn't know
# what he knows. These are reported, never proposed for a move.
TERMINAL_ATTIO_STAGES = {"passed", "invested", "closed", "lost"}

# Hub stages that are real tabs (hub-next/src/lib/stages.js). 'new' is the
# internal triage bucket -- a company sitting there is effectively unplaced,
# which is why it counts as a mismatch rather than as agreement.
HUB_UNPLACED_STAGES = {None, "", "new"}


# ── normalization ────────────────────────────────────────────────────────────

_LEGAL_SUFFIX_RE = re.compile(
    r"\s\b(inc|llc|ltd|limited|corp|corporation|co|sa|ag|gmbh|bv|plc"
    r"|technologies|technology|labs|ai)\b$")


def norm_name(name):
    """Company name -> comparison key. Strips the legal suffixes and spacing
    that make 'Acme, Inc.' and 'Acme' read as two companies.

    Stripped in a LOOP, not once: 'Widget Co, Inc.' carries two suffixes, and a
    single pass leaves 'widget co' while plain 'Widget Co' reduces to 'widget' --
    so the one-pass version made the two names MORE different than it found them,
    which is the opposite of the point. Only a suffix preceded by a space is
    stripped, so 'Console' keeps its 'co' and 'Nvidia' its 'ai'."""
    n = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).strip()
    while True:
        stripped = _LEGAL_SUFFIX_RE.sub("", n).strip()
        if stripped == n or not stripped:
            break
        n = stripped
    return re.sub(r"\s+", "", n)


def _first_domain(value):
    """The CSV packs several domains into one cell; the hub stores one string."""
    if isinstance(value, list):
        value = value[0] if value else ""
    return normalize_domain(str(value or "").split(",")[0].strip())


# ── Attio side ───────────────────────────────────────────────────────────────

def attio_companies_from_csv(csv_path):
    """One record per COMPANY (not per deal) off an Attio Deals CSV export."""
    rows = list(read_rows(csv_path))
    return _attio_companies_from_rows(rows)


def _attio_companies_from_rows(rows):
    out = {}
    for key, group in group_by_company(rows).items():
        auth = authoritative_row(group)
        names = sorted({n for r in group for n in r["investor_names"]})
        domains = sorted({d for r in group for d in r["investor_domains"]})
        out[key] = {
            "key": key,
            "name": auth["name"],
            "domain": _first_domain(auth["domain"]),
            "series": auth["series"],
            "stage": auth["stage"],
            "record_id": auth.get("record_id") or "",
            "deal_date": auth["deal_date"],
            "investors": names,
            "investorDomains": domains,
            "top10": tier1_firms.match_top10(investor_domains=domains, investor_names=names),
            "tier1_33": tier1_firms.match_tier1_33(investor_names=names),
            "rounds": sorted({r["series"] for r in group if r["series"]}),
            # EVERY deal's stage, not just the authoritative row's. Placement
            # compares against the current stage, but history is cumulative:
            # a company with a Passed deal in May and a Qualified one in June
            # WAS passed on, and the hub is supposed to keep that. Reading only
            # the latest row silently dropped the `passed` tag for exactly the
            # companies that have been round the loop more than once (Warp,
            # Anthropic, Legora, Jump AI in the 2026-08-13 export).
            "allStages": sorted({r["stage"] for r in group if r["stage"]}),
            "dealCount": len(group),
        }
    return out


def dump_attio_snapshot(out_path):
    """Pulls every Deal over the Attio API into the same row shape read_rows()
    yields off the CSV, so both sources feed one reconciler. Two paginated
    queries total -- deals, then companies -- and the investor/company domains
    are resolved from that one companies map rather than with the per-record GET
    attio_io._company_domain does (a few hundred deals x a few investors each is
    a few thousand round trips otherwise)."""
    from .net import session   # local import: only the --refresh path needs it

    if not config.ATTIO_API_KEY:
        raise RuntimeError("ATTIO_API_KEY not set -- run this in Cloud Shell, or "
                           "use --attio-csv with an export from Attio's UI")
    headers = {"Authorization": f"Bearer {config.ATTIO_API_KEY}",
               "Content-Type": "application/json"}

    def _query_all(obj):
        records, offset, limit = [], 0, 500
        while True:
            r = session.post(f"{config.ATTIO_BASE}/objects/{obj}/records/query",
                             json={"limit": limit, "offset": offset},
                             headers=headers, timeout=90)
            r.raise_for_status()
            batch = r.json().get("data", [])
            records.extend(batch)
            if len(batch) < limit:
                return records
            offset += limit

    deals = _query_all(config.DEALS_OBJECT)
    companies = _query_all("companies")
    print(f"Attio: {len(deals)} deals, {len(companies)} companies")

    by_id = {}
    for rec in companies:
        rid = rec.get("id", {}).get("record_id")
        vals = rec.get("values", {})
        name = _scalar(vals.get("name"))
        domains = [d.get("domain") for d in (vals.get("domains") or [])
                   if isinstance(d, dict) and d.get("domain")]
        by_id[rid] = {"name": name, "domain": domains[0] if domains else ""}

    s = config.READ_SLUGS
    rows = []
    for rec in deals:
        vals = rec.get("values", {})
        company = by_id.get(_ref_id(vals.get("associated_company")), {})
        inv_ids = _ref_ids(vals.get(s["investors_ref"]))
        rows.append({
            "record_id": rec.get("id", {}).get("record_id") or "",
            "name": _scalar(vals.get(s["name"])) or company.get("name") or "(unnamed deal)",
            "domain": company.get("domain") or "",
            "stage": _scalar(vals.get(config.STAGE_SLUG)) or "",
            "stage_changed_at": "",
            "deal_date": _scalar(vals.get(s["round_date"])) or "",
            "series": _scalar(vals.get(s["round"])) or "",
            "description": _scalar(vals.get(s["description"])) or "",
            # Named investors come off the linked Companies records; the free-text
            # lead/new investor fields are folded in so a deal whose links were
            # never resolved still contributes names to the Top 10 / Tier 1 match.
            "investor_names": sorted({by_id[i]["name"] for i in inv_ids if by_id.get(i, {}).get("name")}
                                     | _split_names(_scalar(vals.get(s["lead_investors"])))),
            "investor_domains": sorted({by_id[i]["domain"] for i in inv_ids if by_id.get(i, {}).get("domain")}),
            "access": "",
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path} ({len(rows)} deal rows)")
    return rows


def _scalar(cell_list):
    """Attio wraps every value in a list of typed cells -- same best-effort read
    attio_io._value does, kept local so this module doesn't depend on it."""
    if not cell_list:
        return None
    cell = cell_list[0] if isinstance(cell_list, list) else cell_list
    if not isinstance(cell, dict):
        return cell
    for k in ("value", "option", "status", "full_name", "currency_value"):
        if k in cell:
            inner = cell[k]
            return inner.get("title") if isinstance(inner, dict) else inner
    return None


def _ref_id(cell_list):
    ids = _ref_ids(cell_list)
    return ids[0] if ids else None


def _ref_ids(cell_list):
    if not isinstance(cell_list, list):
        return []
    return [c.get("target_record_id") for c in cell_list
            if isinstance(c, dict) and c.get("target_record_id")]


def _split_names(text):
    return {p.strip() for p in re.split(r"[,;]", str(text or "")) if p.strip()}


# ── hub side ─────────────────────────────────────────────────────────────────

def hub_companies_from_snapshot(snapshot):
    """Collapses the raw `companies` dump into one record per company. The
    per-round docs the hub creates (`${companyKey}--${roundSlug}`, see
    import_attio_deals_csv and hub-next's createAdditionalRound) fold into their
    parent instead of counting as separate companies -- otherwise every
    multi-round company reports as an extra hub-only finding."""
    primaries, extras = {}, defaultdict(list)
    for doc in snapshot:
        doc_id = doc.get("id") or ""
        if "--" in doc_id:
            # A round doc. Its parent is companyKey when set, else the id prefix.
            extras[doc.get("companyKey") or doc_id.split("--", 1)[0]].append(doc)
            continue
        primaries[doc_id] = doc

    out = {}
    for key, doc in primaries.items():
        rounds = extras.get(key, [])
        investors = list(doc.get("investors") or [])
        domains = list(doc.get("investorDomains") or [])
        origin = doc.get("origin") or {}
        out[key] = {
            "key": key,
            "name": doc.get("name") or key,
            "domain": _first_domain(doc.get("website")),
            "series": doc.get("round") or origin.get("round") or "",
            "stage": doc.get("stage"),
            "tags": list(doc.get("tags") or []),
            "attioRecordId": origin.get("attioRecordId") or "",
            "attioStage": origin.get("attioStage") or "",
            "originSource": origin.get("source") or "",
            "investors": investors,
            "investorDomains": domains,
            # Recomputed from the cap table rather than trusting the stored
            # top10Investors/tier1_33Investors fields -- those were written by
            # past runs and are exactly the kind of thing this report exists to
            # catch drifting. The stored values are reported alongside.
            "top10": tier1_firms.match_top10(investor_domains=domains, investor_names=investors),
            "tier1_33": tier1_firms.match_tier1_33(investor_names=investors),
            "storedTop10VC": bool(doc.get("top10VC")),
            "extraRoundDocs": len(rounds),
            "latestScreen": doc.get("latestScreen"),
            # Which keys the doc actually carries a value for -- what
            # find_hub_duplicates diffs to report data stranded on an orphan.
            "presentFields": sorted(k for k, v in doc.items()
                                    if v not in (None, "", [], {})),
        }
    for orphan_key, docs in extras.items():
        if orphan_key in out:
            continue
        # A round doc whose parent is missing from the dump -- rare, but it is a
        # real company in the hub and must not vanish from the reconciliation.
        doc = docs[0]
        out[orphan_key] = {
            "key": orphan_key, "name": doc.get("name") or orphan_key,
            "domain": _first_domain(doc.get("website")), "series": doc.get("round") or "",
            "stage": doc.get("stage"), "tags": list(doc.get("tags") or []),
            "attioRecordId": "", "attioStage": "", "originSource": "orphan-round-doc",
            "investors": [], "investorDomains": [], "top10": [], "tier1_33": [],
            "storedTop10VC": bool(doc.get("top10VC")), "extraRoundDocs": len(docs),
            "latestScreen": doc.get("latestScreen"),
            "presentFields": sorted(k for k, v in doc.items() if v not in (None, "", [], {})),
        }
    return out


# Fields whose absence from a duplicate says nothing -- every doc has them, so
# diffing them just adds noise to the stranded-data report.
_UNINTERESTING_FIELDS = {"id", "name", "website", "companyKey"}

# The screen-deals Firestore test backfill left fixture companies behind on
# `.example` domains. They are not real deals and must not read as "in the hub,
# missing from Attio" -- Attio is right not to have them.
TEST_DOMAIN_SUFFIX = ".example"


def find_hub_duplicates(hub):
    """Two hub docs for one company, clustered by normalized name and by domain.

    This is a hub-vs-hub problem, not an Attio one, but it surfaces HERE because
    it masquerades as a sync gap: the domain-keyed doc matches its Attio deal and
    the name-keyed twin is left over, so it reports as "in the hub, missing from
    Attio" when Attio is not missing anything.

    The cause is `fit_note.company_id`'s domain-first, name-slug-fallback rule.
    An Attio Deal carries no `domain` attribute of its own (it hangs off the
    linked Company record -- see attio_io._company_domain), so a screening run
    that could not resolve it fell back to the name slug and wrote a SECOND doc.
    The screen result then lands on the twin while the real company shows no
    score at all, which is why `stranded` is reported per pair: it is the
    difference that is actually lost, not just a tidiness issue.

    Returns [{primary, duplicates: [{key, stranded}]}], primary being the doc
    with the real placement (an Attio origin, then a stage, then most fields)."""
    parent = {k: k for k in hub}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for attr in ("name", "domain"):
        buckets = defaultdict(list)
        for key, row in hub.items():
            val = norm_name(row["name"]) if attr == "name" else row["domain"]
            if val:
                buckets[val].append(key)
        for keys in buckets.values():
            for other in keys[1:]:
                union(keys[0], other)

    clusters = defaultdict(list)
    for key in hub:
        clusters[find(key)].append(key)

    def substance(key):
        row = hub[key]
        return (row["originSource"] == "attio", bool(row["stage"]), len(row["presentFields"]))

    out = []
    for keys in clusters.values():
        if len(keys) < 2:
            continue
        keys = sorted(keys, key=substance, reverse=True)
        primary, dups = hub[keys[0]], []
        for k in keys[1:]:
            row = hub[k]
            stranded = sorted(set(row["presentFields"]) - set(primary["presentFields"])
                              - _UNINTERESTING_FIELDS)
            dups.append({"key": k, "name": row["name"], "stage": row["stage"],
                         "stranded": stranded, "latestScreen": row["latestScreen"]})
        out.append({"primaryKey": keys[0], "name": primary["name"],
                    "primaryStage": primary["stage"], "duplicates": dups})
    return sorted(out, key=lambda d: d["name"])


def dump_hub_snapshot(out_path):
    """Same read export_companies_snapshot.py does, inlined so --refresh is one
    command instead of two. Read-only."""
    from google.cloud import firestore   # local import: only --refresh needs it
    from .export_companies_snapshot import _jsonable

    db = firestore.Client(project=config.GCP_PROJECT_ID)
    docs = list(db.collection("companies").stream())
    snapshot = [{"id": d.id, **_jsonable(d.to_dict())} for d in docs]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)
    print(f"Wrote {out_path} ({len(snapshot)} company docs)")
    return snapshot


# ── matching ─────────────────────────────────────────────────────────────────

def link(hub, attio):
    """Pairs the two sides up. Returns (matched, hub_only, attio_only) where
    matched is a list of (hub_row, attio_row, basis).

    Three passes, most reliable first: same company key, then same website
    domain, then same normalized name. Each pass only considers rows no earlier
    pass has claimed, so one hub company can never be matched to two deals."""
    matched, used_hub, used_attio = [], set(), set()

    for key in sorted(set(hub) & set(attio)):
        matched.append((hub[key], attio[key], "key"))
        used_hub.add(key)
        used_attio.add(key)

    for basis, keyfn in (("domain", lambda r: r["domain"]),
                         ("name", lambda r: norm_name(r["name"]))):
        index = defaultdict(list)
        for k, row in hub.items():
            if k not in used_hub and keyfn(row):
                index[keyfn(row)].append(k)
        for k, row in sorted(attio.items()):
            if k in used_attio or not keyfn(row):
                continue
            candidates = [c for c in index.get(keyfn(row), []) if c not in used_hub]
            if not candidates:
                continue
            hk = candidates[0]
            matched.append((hub[hk], row, basis))
            used_hub.add(hk)
            used_attio.add(k)

    hub_only = [hub[k] for k in sorted(hub) if k not in used_hub]
    attio_only = [attio[k] for k in sorted(attio) if k not in used_attio]
    return matched, hub_only, attio_only


# ── the report ───────────────────────────────────────────────────────────────

def _expected(row, series_b_mode):
    """Cap-table membership is derived from the row's investor list here rather
    than read off its precomputed top10/tier1_33 fields, so a one-sided row goes
    through the exact same derivation as a matched pair (which unions the two
    sides' investors before matching). One source of truth for the placement
    inputs -- otherwise a caller that fills `investors` but not `top10` silently
    gets "the rule places this nowhere" for a Sequoia-backed Series C."""
    top10 = tier1_firms.match_top10(investor_domains=row.get("investorDomains"),
                                    investor_names=row.get("investors"))
    tier1_33 = tier1_firms.match_tier1_33(investor_names=row.get("investors"))
    return expected_placement(row.get("series"), top10, tier1_33,
                              series_b_mode=series_b_mode)


def attio_stage_tags(attio_stage):
    """The hub tags implied by Attio's OWN stage, independent of the series rule.

    Two different questions get answered by two different mechanisms, and this
    is the second one. `expected_placement` asks "where does the rule say this
    belongs?" and yields qualified/radar. This asks "what has actually happened
    to this deal?" and yields pipeline/passed/invested/watchlist -- history, not
    mandate. A deal can be Qualified by the rule and Passed in fact; the hub
    holds both because its membership is additive, which is the whole reason
    Oscar wants the double tag (2026-08-13: "the ones we've passed used to be in
    pipeline in attio, but in the hub we can double tag them as both pipeline
    and passed").

    `passed` implies `pipeline` -- passing on a deal means it was actually
    evaluated, so it belongs in Pipeline's history too. Same rule
    import_attio_deals_csv already applies; shared here so the one-shot CSV
    import and the ongoing reconciler cannot drift apart on it.

    Returns [] for an Attio stage that maps to no hub bucket, rather than
    guessing."""
    stage = str(attio_stage or "").strip().lower()
    mapped = config.ATTIO_STAGE_MAP.get(stage)
    if stage == PASSED_STAGE:
        # 'passed' is not in ATTIO_STAGE_MAP -- it is a hub tag, not a stage.
        return [PASSED_TAG, "pipeline"]
    return [mapped] if mapped else []


def _hub_buckets(hub_row):
    """Every tab a hub company shows up in: hub-next models membership as
    {stage} u tags, so a Qualified company tagged `radar` is in both."""
    return {str(hub_row.get("stage") or "").lower()} | {
        str(t).lower() for t in (hub_row.get("tags") or [])}


def reconcile(hub, attio, series_b_mode="dual", names=None):
    """Pure diff over the two already-normalized sides. No I/O."""
    matched, hub_only, attio_only = link(hub, attio)

    # Three things get pulled out of hub_only before it is reported, because
    # none of them means "Attio is missing this deal":
    #   - a duplicate of a hub company that DID match (see find_hub_duplicates)
    #   - a `.example` test fixture from the screen-deals Firestore backfill
    # What survives is the real answer to "in the hub, not in Attio".
    duplicates = find_hub_duplicates(hub)
    dup_keys = {d["key"] for group in duplicates for d in group["duplicates"]}
    matched_keys = {h["key"] for h, _, _ in matched}
    # Only a duplicate of a company that actually matched is explained away; a
    # cluster where NO doc reached Attio is still a genuine hub-only company.
    explained = {k for group in duplicates if group["primaryKey"] in matched_keys
                 for k in [d["key"] for d in group["duplicates"]]}
    test_fixtures = [r for r in hub_only if r["domain"].endswith(TEST_DOMAIN_SUFFIX)]
    fixture_keys = {r["key"] for r in test_fixtures}
    hub_dupes_only = [r for r in hub_only if r["key"] in explained and r["key"] not in fixture_keys]
    hub_only = [r for r in hub_only
                if r["key"] not in explained and r["key"] not in fixture_keys]

    for row in attio_only:
        stage, tags, why = _expected(row, series_b_mode)
        row["expectedHubStage"] = stage
        row["expectedHubTags"] = tags
        row["expectedWhy"] = why

    for row in hub_only:
        stage, tags, why = _expected(row, series_b_mode)
        row["expectedAttioStage"] = stage
        row["expectedWhy"] = why

    mismatches, agreed, unplaced_above_b, human_filed, unplaced = [], [], [], [], []
    history_gaps = []
    for hub_row, attio_row, basis in matched:
        # The cap table is the union of what each side knows -- either side can
        # be the one carrying the investor list for a given company.
        names_u = sorted(set(hub_row["investors"]) | set(attio_row["investors"]))
        domains_u = sorted(set(hub_row["investorDomains"]) | set(attio_row["investorDomains"]))
        merged = {
            "series": attio_row["series"] or hub_row["series"],
            "investors": names_u, "investorDomains": domains_u,
        }
        stage, tags, why = _expected(merged, series_b_mode)
        merged["top10"] = tier1_firms.match_top10(investor_domains=domains_u, investor_names=names_u)
        merged["tier1_33"] = tier1_firms.match_tier1_33(investor_names=names_u)
        attio_stage = str(attio_row["stage"] or "").strip().lower()
        buckets = _hub_buckets(hub_row)
        expected_buckets = ({stage.lower()} | {t.lower() for t in tags}) if stage else set()

        record = {
            "key": hub_row["key"], "attioKey": attio_row["key"], "name": hub_row["name"],
            "matchBasis": basis, "series": merged["series"],
            "band": series_band(merged["series"]),
            "attioStage": attio_row["stage"], "hubStage": hub_row.get("stage"),
            "hubTags": hub_row.get("tags") or [], "expectedStage": stage,
            "expectedTags": tags, "expectedWhy": why,
            "top10": merged["top10"], "tier1_33": merged["tier1_33"],
            "attioRecordId": attio_row.get("record_id") or hub_row.get("attioRecordId") or "",
            "attioAllStages": attio_row.get("allStages") or [],
        }

        # Attio's stage is DEAL HISTORY and applies to every matched company,
        # including the Passed/Invested ones the series rule must not touch --
        # in fact especially those, since "was in pipeline, then passed" is
        # exactly the history the hub is supposed to keep. Computed before the
        # terminal-stage branch below so it isn't skipped for them.
        history = sorted({t for st in (attio_row.get("allStages") or [attio_row["stage"]])
                          for t in attio_stage_tags(st)})
        record["attioHistoryTags"] = history
        record["historyMissing"] = sorted(set(history) - buckets)
        if record["historyMissing"]:
            # Tracked in its own list because these cut ACROSS the five
            # placement buckets -- a Passed deal, an agreeing Qualified one and
            # an unplaced one can each be missing its history tag.
            history_gaps.append(record)

        if attio_stage in TERMINAL_ATTIO_STAGES:
            # Filed by hand and settled -- the series rule is not applied. The
            # history tags above still are: those record what happened, not
            # where the rule thinks it belongs.
            human_filed.append(record)
            continue
        if stage is None:
            # The rule places these nowhere. They are NOT dropped -- every
            # matched deal lands in exactly one of these buckets, so the section
            # counts add up to `matched` and nothing goes missing between them.
            (unplaced_above_b if record["band"] == BAND_ABOVE_B else unplaced).append(record)
            continue
        if expected_buckets <= buckets and attio_stage == stage.lower():
            agreed.append(record)
        else:
            missing = sorted(expected_buckets - buckets)
            # Two genuinely different hub actions, kept apart because they carry
            # different risk. A company sitting in the hub's `new` triage bucket
            # (or with no stage at all) has never been placed, so the fix is to
            # SET its primary stage. A company already in a real tab was put
            # there by someone -- possibly by hand -- so the fix is the additive
            # tag, which composes with their choice instead of overwriting it.
            # apply_hub honours the split; only the report ever conflates them.
            hub_unplaced = str(hub_row.get("stage") or "").lower() in {s or "" for s in HUB_UNPLACED_STAGES}
            if hub_unplaced and missing:
                record["hubSetStage"] = stage.lower()
                # Anything beyond the primary (i.e. the additive `radar` on a
                # Top 10-backed Series B) still rides along as a tag.
                record["hubAddTags"] = [t for t in missing if t != stage.lower()]
            else:
                record["hubSetStage"] = None
                record["hubAddTags"] = missing
            record["hubNeeds"] = missing
            record["attioNeeds"] = None if attio_stage == stage.lower() else stage
            mismatches.append(record)

    # The one band the two readings of Oscar's rule disagree on -- reported with
    # names so the default isn't an invisible choice. See expected_placement.
    b_top10 = [r for r in ([m for m in mismatches] + agreed + human_filed)
               if r["band"] == BAND_B and r["top10"]]

    return {
        "counts": {
            "hubCompanies": len(hub), "attioCompanies": len(attio),
            "matched": len(matched), "hubOnly": len(hub_only), "attioOnly": len(attio_only),
            "placementMismatches": len(mismatches), "placementAgreed": len(agreed),
            "humanFiled": len(human_filed), "aboveBNoTier33": len(unplaced_above_b),
            "unplacedByRule": len(unplaced), "seriesBTop10": len(b_top10),
            "hubDuplicateCompanies": len(duplicates),
            "hubDuplicateDocs": len(dup_keys),
            "hubDuplicatesShownAsHubOnly": len(hub_dupes_only),
            "testFixtures": len(test_fixtures),
            "historyGaps": len(history_gaps),
        },
        "historyGaps": history_gaps,
        "hubDuplicates": duplicates,
        "testFixtures": test_fixtures,
        "seriesBMode": series_b_mode,
        "attioOnly": attio_only,
        "hubOnly": hub_only,
        "mismatches": mismatches,
        "humanFiled": human_filed,
        "aboveBNoTier33": unplaced_above_b,
        "unplacedByRule": unplaced,
        "unplacedReasons": Counter(r["expectedWhy"] for r in unplaced),
        "seriesBTop10": b_top10,
        "matchBasis": Counter(b for _, _, b in matched),
        "namesCheck": check_names(names, hub, attio) if names else None,
    }


def check_names(names, hub, attio):
    """Oscar's hand-written list of companies that should be in the pipeline on
    both sides -> where each one actually is."""
    hub_by_name = {norm_name(r["name"]): r for r in hub.values()}
    attio_by_name = {norm_name(r["name"]): r for r in attio.values()}
    out = []
    for raw in names:
        n = norm_name(raw)
        h, a = hub_by_name.get(n) or hub.get(slugify(raw)), attio_by_name.get(n) or attio.get(slugify(raw))
        out.append({
            "input": raw,
            "inHub": bool(h), "inAttio": bool(a),
            "hubStage": (h or {}).get("stage"), "hubTags": (h or {}).get("tags") or [],
            "attioStage": (a or {}).get("stage"),
            "series": (a or {}).get("series") or (h or {}).get("series") or "",
        })
    return out


def read_names_file(path):
    """One company name per line, or a CSV whose first column is the name.
    Blank lines and `#` comments ignored."""
    names = []
    with open(path, newline="", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # csv.reader on the RAW line -- stripping quotes first would turn
            # a quoted '"Beta, Inc."' into two fields and keep only 'Beta'.
            names.append((next(csv.reader([line]), [line]) or [line])[0].strip())
    return [n for n in names if n]


# ── output ───────────────────────────────────────────────────────────────────

def _hub_display(r):
    """`stage + tags`, deduped -- a company whose stage IS radar and which also
    carries the radar tag should read 'radar', not 'radar +radar'."""
    extra = [t for t in (r.get("hubTags") or []) if str(t).lower() != str(r.get("hubStage") or "").lower()]
    return f"{r.get('hubStage')}" + (f" +{','.join(extra)}" if extra else "")


def _hub_fix(r):
    """The two hub actions read differently and must not be conflated: setting an
    unplaced company's primary stage vs. adding a tag to one already filed."""
    bits = []
    if r.get("hubSetStage"):
        bits.append(f"stage -> {r['hubSetStage']}")
    if r.get("hubAddTags"):
        bits.append("+tag " + ", ".join(r["hubAddTags"]))
    return "; ".join(bits) or "-"


def _table(rows, cols):
    head = "| " + " | ".join(c[0] for c in cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    body = ["| " + " | ".join(str(c[1](r) or "").replace("|", "/") for c in cols) + " |"
            for r in rows]
    return "\n".join([head, sep] + body)


def render_markdown(report, run_date):
    c = report["counts"]
    L = [
        f"# Attio <-> Hub deal sync -- {run_date}",
        "",
        f"- Attio companies (deals grouped by company): **{c['attioCompanies']}**",
        f"- Hub companies (Firestore `companies`, round docs folded in): **{c['hubCompanies']}**",
        f"- Matched on both sides: **{c['matched']}** "
        f"({', '.join(f'{n} by {b}' for b, n in report['matchBasis'].most_common())})",
        f"- **In Attio, missing from the hub: {c['attioOnly']}**",
        f"- **In the hub, missing from Attio: {c['hubOnly']}** "
        f"(after setting aside {c['hubDuplicateDocs']} duplicate hub docs and "
        f"{c['testFixtures']} test fixtures)",
        f"- Placement disagreements among matched deals: **{c['placementMismatches']}** "
        f"(agreed: {c['placementAgreed']})",
        f"- Matched but filed by hand in Attio (Passed/Invested -- rule not applied): {c['humanFiled']}",
        f"- **Missing their Attio deal history in the hub (pipeline/passed/invested tags): "
        f"{c['historyGaps']}**",
        f"- Matched but the rule places them nowhere: {c['unplacedByRule'] + c['aboveBNoTier33']} "
        f"({c['aboveBNoTier33']} above B with no Tier 1 (33), {c['unplacedByRule']} below/unknown series)",
        "",
        f"Those five buckets partition the {c['matched']} matched companies "
        f"({c['placementMismatches']} + {c['placementAgreed']} + {c['humanFiled']} + "
        f"{c['aboveBNoTier33']} + {c['unplacedByRule']} = "
        f"{c['placementMismatches'] + c['placementAgreed'] + c['humanFiled'] + c['aboveBNoTier33'] + c['unplacedByRule']}), "
        "so no matched deal is missing from the report.",
        "",
        "Placement rule applied: **Tier 1 (33) investor + above Series B -> Qualified**; "
        "**Top 10 investor + Series B or below -> Radar**. "
        f"Series-B mode: `{report['seriesBMode']}`.",
        "",
    ]

    if report["namesCheck"]:
        L += ["## Your pipeline list", "",
              _table(report["namesCheck"], [
                  ("Company", lambda r: r["input"]),
                  ("In Attio", lambda r: ("yes -- " + str(r["attioStage"] or "no stage")) if r["inAttio"] else "**MISSING**"),
                  ("In hub", lambda r: ("yes -- " + str(r["hubStage"] or "no stage")) if r["inHub"] else "**MISSING**"),
                  ("Series", lambda r: r["series"]),
                  ("Hub tags", lambda r: ", ".join(r["hubTags"])),
              ]), ""]

    L += ["## In Attio, missing from the hub", "",
          f"{c['attioOnly']} companies. `Should be` is where the rule puts them; "
          "a blank means the rule places them nowhere (below mandate, or no "
          "Tier 1 backer) -- those need a human call, not an automatic push.", "",
          _table(sorted(report["attioOnly"], key=lambda r: (r["expectedHubStage"] or "zzz", r["name"])), [
              ("Company", lambda r: r["name"]),
              ("Domain", lambda r: r["domain"]),
              ("Series", lambda r: r["series"]),
              ("Attio stage", lambda r: r["stage"]),
              ("Should be", lambda r: " + ".join([r["expectedHubStage"] or "--"] + r["expectedHubTags"])),
              ("Top 10 / Tier 1 (33)", lambda r: ", ".join(r["top10"] or r["tier1_33"][:3])),
          ]), ""]

    L += ["## Duplicate hub docs", "",
          f"{c['hubDuplicateCompanies']} companies hold {c['hubDuplicateDocs']} extra doc(s) "
          "between them -- one keyed by domain, its twin keyed by the name slug. "
          "`fit_note.company_id` prefers the domain and falls back to the name, and an "
          "Attio Deal carries no domain of its own, so a screening run that could not "
          "resolve it wrote a second doc. **`Stranded` is data sitting on the twin that "
          "the real company doc does not have** -- most importantly `latestScreen`, which "
          "is why these companies show no fit score in the hub despite having been "
          f"screened. {c['hubDuplicatesShownAsHubOnly']} of them would otherwise have "
          "reported as \"missing from Attio\", which they are not.", "",
          _table([{**d, "primary": g["primaryKey"], "pname": g["name"],
                   "pstage": g["primaryStage"]}
                  for g in report["hubDuplicates"] for d in g["duplicates"]], [
              ("Company", lambda r: r["pname"]),
              ("Real doc", lambda r: f"{r['primary']} ({r['pstage'] or 'no stage'})"),
              ("Duplicate doc", lambda r: r["key"]),
              ("Stranded on the duplicate", lambda r: ", ".join(r["stranded"]) or "-"),
              ("Screen on duplicate", lambda r: (f"{r['latestScreen'].get('fitScore')} "
                                                 f"gate={r['latestScreen'].get('gate')}")
                                                if r["latestScreen"] else "-"),
          ]), ""]

    if report["testFixtures"]:
        L += ["## Test fixtures (not real deals)", "",
              f"{c['testFixtures']} hub companies on `{TEST_DOMAIN_SUFFIX}` domains, left over "
              "from the screen-deals Firestore test backfill. Excluded from the hub-only list "
              "below -- Attio is right not to have them.", "",
              ", ".join(f"{r['name']} (`{r['key']}`)" for r in report["testFixtures"]), ""]

    L += ["## In the hub, missing from Attio", "",
          f"{c['hubOnly']} companies, after excluding the duplicate docs and test "
          "fixtures above.", "",
          _table(sorted(report["hubOnly"], key=lambda r: (str(r["stage"]), r["name"])), [
              ("Company", lambda r: r["name"]),
              ("Domain", lambda r: r["domain"]),
              ("Series", lambda r: r["series"]),
              ("Hub stage", lambda r: r["stage"]),
              ("Hub tags", lambda r: ", ".join(r["tags"])),
              ("Origin", lambda r: r["originSource"]),
              ("Should be in Attio", lambda r: r["expectedAttioStage"] or "--"),
          ]), ""]

    L += ["## Placement disagreements", "",
          "Matched on both sides, but at least one side isn't where the rule says "
          "it should be. `Hub needs` lists the tabs the company is missing from "
          "(hub membership is additive: stage + tags).", "",
          _table(sorted(report["mismatches"], key=lambda r: r["name"]), [
              ("Company", lambda r: r["name"]),
              ("Series", lambda r: r["series"]),
              ("Attio", lambda r: r["attioStage"]),
              ("Hub", lambda r: _hub_display(r)),
              ("Should be", lambda r: " + ".join([r["expectedStage"] or "--"] + r["expectedTags"])),
              ("Hub fix", lambda r: _hub_fix(r)),
              ("Attio fix", lambda r: f"stage -> {r['attioNeeds']}" if r["attioNeeds"] else "-"),
              ("Why", lambda r: r["expectedWhy"]),
          ]), ""]

    L += ["## Missing deal history (pipeline / passed / invested)", "",
          f"{c['historyGaps']} companies whose Attio stage implies a hub bucket the hub "
          "isn't carrying. This is separate from the placement rule above: the rule says "
          "where a deal *belongs* (qualified/radar), this says what actually *happened* to "
          "it. Both are additive in the hub, so a deal can be Qualified by the rule and "
          "Passed in fact. `passed` always brings `pipeline` with it -- passing on a deal "
          "means it was evaluated, so it belongs in Pipeline's history too.", "",
          _table(sorted(report["historyGaps"], key=lambda r: r["name"]), [
              ("Company", lambda r: r["name"]),
              ("Attio stage(s)", lambda r: ", ".join(r["attioAllStages"]) or r["attioStage"]),
              ("Hub now", lambda r: _hub_display(r)),
              ("Missing tags", lambda r: ", ".join(r["historyMissing"])),
          ]), ""]

    L += ["## Above Series B, no Tier 1 (33) investor", "",
          f"{c['aboveBNoTier33']} matched companies clear the B+ mandate but have no "
          "Tier 1 (33) firm on the cap table, so the Qualified clause of the rule "
          "does not fire. The live intake path files these as Qualified anyway "
          "(`determine_placement` never checks Tier 1) -- this is the population "
          "affected by that difference.", "",
          _table(sorted(report["aboveBNoTier33"], key=lambda r: r["name"])[:80], [
              ("Company", lambda r: r["name"]),
              ("Series", lambda r: r["series"]),
              ("Attio", lambda r: r["attioStage"]),
              ("Hub", lambda r: r["hubStage"]),
              ("Investors on file", lambda r: len(r["tier1_33"]) and ", ".join(r["tier1_33"]) or "none matched"),
          ]), ""]

    L += ["## Matched, but the rule places them nowhere", "",
          f"{c['unplacedByRule']} companies below Series B without a Top 10 backer, or with "
          "no usable series on file. They stay wherever they are today -- listed so the "
          "numbers above reconcile and so a wrong/blank Series is visible as the cause.", "",
          "\n".join(f"- {why}: **{n}**" for why, n in report["unplacedReasons"].most_common()), "",
          _table(sorted(report["unplacedByRule"], key=lambda r: (r["band"], r["name"]))[:120], [
              ("Company", lambda r: r["name"]),
              ("Series", lambda r: r["series"] or "(blank)"),
              ("Attio", lambda r: r["attioStage"]),
              ("Hub", lambda r: _hub_display(r)),
              ("Why", lambda r: r["expectedWhy"]),
          ]), ""]

    L += ["## Series B with a Top 10 investor", "",
          f"{c['seriesBTop10']} companies sit in the one band the rule reads two ways. "
          "Under `dual` (the default, and what the shipped intake code does) they are "
          "Qualified in Attio and additionally tagged `radar` in the hub. Under "
          "`radar` they would be Radar only. Rerun with `--series-b-mode radar` to "
          "see that version.", "",
          _table(sorted(report["seriesBTop10"], key=lambda r: r["name"]), [
              ("Company", lambda r: r["name"]),
              ("Series", lambda r: r["series"]),
              ("Attio", lambda r: r["attioStage"]),
              ("Hub", lambda r: f"{r['hubStage']}" + (f" +{','.join(r['hubTags'])}" if r["hubTags"] else "")),
              ("Top 10", lambda r: ", ".join(r["top10"])),
          ]), ""]

    L += ["## Filed by hand in Attio (Passed / Invested)", "",
          f"{c['humanFiled']} matched companies carry a stage the series rule must not "
          "override. Listed so nothing is invisible; no action proposed.", "",
          ", ".join(sorted(f"{r['name']} ({r['attioStage']})" for r in report["humanFiled"])) or "none",
          ""]
    return "\n".join(L)


def write_csvs(report, out_dir, run_date):
    paths = []
    specs = [
        ("attio-not-in-hub", report["attioOnly"],
         ["name", "domain", "series", "stage", "expectedHubStage", "expectedWhy", "record_id"]),
        ("hub-not-in-attio", report["hubOnly"],
         ["name", "domain", "series", "stage", "expectedAttioStage", "expectedWhy", "originSource", "key"]),
        ("placement-mismatches", report["mismatches"],
         ["name", "series", "attioStage", "hubStage", "hubTags", "expectedStage",
          "expectedTags", "hubSetStage", "hubAddTags", "attioNeeds", "expectedWhy",
          "attioRecordId", "key"]),
        ("unplaced-by-rule", report["unplacedByRule"] + report["aboveBNoTier33"],
         ["name", "series", "band", "attioStage", "hubStage", "expectedWhy", "key"]),
        ("history-tag-gaps", report["historyGaps"],
         ["name", "attioStage", "attioAllStages", "hubStage", "hubTags",
          "attioHistoryTags", "historyMissing", "key"]),
        ("hub-duplicate-docs",
         [{"company": g["name"], "primaryKey": g["primaryKey"], "primaryStage": g["primaryStage"],
           "duplicateKey": d["key"], "stranded": d["stranded"],
           "duplicateScreen": (d["latestScreen"] or {}).get("fitScore"),
           "duplicateScreenGate": (d["latestScreen"] or {}).get("gate")}
          for g in report["hubDuplicates"] for d in g["duplicates"]],
         ["company", "primaryKey", "primaryStage", "duplicateKey", "stranded",
          "duplicateScreen", "duplicateScreenGate"]),
    ]
    for label, rows, cols in specs:
        path = os.path.join(out_dir, f"deal-sync-{label}-{run_date}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow([", ".join(map(str, r.get(c))) if isinstance(r.get(c), list) else (r.get(c) or "")
                            for c in cols])
        paths.append(path)
    return paths


# ── apply (both directions, dry-run unless --yes) ────────────────────────────

def apply_hub(report, yes=False):
    """Creates the hub company docs for deals the rule places but the hub is
    missing, and adds the missing additive tags on placement mismatches. Only
    ever ADDS -- never rewrites an existing `stage`, same don't-clobber rule
    firestore_push and import_attio_deals_csv already follow, because a hub
    stage can be a deliberate hand edit."""
    from google.cloud import firestore

    creates = [r for r in report["attioOnly"] if r["expectedHubStage"]]
    stage_sets = [r for r in report["mismatches"] if r.get("hubSetStage")]
    tag_adds = [r for r in report["mismatches"] if r.get("hubAddTags")]
    history_adds = report["historyGaps"]
    print(f"{'DRY RUN -- ' if not yes else ''}hub: {len(creates)} docs to create, "
          f"{len(stage_sets)} unplaced docs to give a stage, {len(tag_adds)} to tag")
    for r in creates:
        print(f"  create {r['key']:<28} {r['name']:<30} stage={r['expectedHubStage'].lower()} "
              f"tags={r['expectedHubTags']}")
    for r in stage_sets:
        print(f"  stage  {r['key']:<28} {r['name']:<30} {r['hubStage']!r} -> {r['hubSetStage']}"
              + (f" +tags {r['hubAddTags']}" if r["hubAddTags"] else ""))
    for r in tag_adds:
        print(f"  tag    {r['key']:<28} {r['name']:<30} += {r['hubAddTags']}")
    print(f"{'DRY RUN -- ' if not yes else ''}hub: {len(history_adds)} to get their Attio "
          f"deal history (pipeline/passed/invested)")
    for r in history_adds:
        print(f"  hist   {r['key']:<28} {r['name']:<30} += {r['historyMissing']} "
              f"(Attio: {r['attioStage']})")
    if not yes:
        return {"created": 0, "staged": 0, "tagged": 0, "history": 0, "dryRun": True}

    db = firestore.Client(project=config.GCP_PROJECT_ID)
    for r in creates:
        payload = {
            "name": r["name"], "website": r["domain"] or None,
            "round": r["series"] or None,
            "stage": r["expectedHubStage"].lower(),
            "latestScreen": None,   # see import_attio_deals_csv -- avoids listCompanies()'s N+1 fallback
            "investors": r["investors"] or None,
            "investorDomains": r["investorDomains"] or None,
            "origin": {"source": "deal-sync", "attioRecordId": r.get("record_id") or None,
                       "attioStage": r["stage"], "importedAt": firestore.SERVER_TIMESTAMP},
        }
        if r["top10"]:
            payload["top10Investors"] = r["top10"]
            payload["top10VC"] = True
        if r["tier1_33"]:
            payload["tier1_33Investors"] = r["tier1_33"]
        if r["expectedHubTags"]:
            payload["tags"] = firestore.ArrayUnion(r["expectedHubTags"])
        db.collection("companies").document(r["key"]).set(
            {k: v for k, v in payload.items() if v is not None or k == "latestScreen"}, merge=True)
    for r in stage_sets:
        # Safe because the company is in the hub's `new`/blank triage bucket --
        # nobody has placed it, so there is no hand-made choice to clobber.
        payload = {"stage": r["hubSetStage"]}
        if r["hubAddTags"]:
            payload["tags"] = firestore.ArrayUnion(r["hubAddTags"])
        db.collection("companies").document(r["key"]).set(payload, merge=True)
    for r in tag_adds:
        db.collection("companies").document(r["key"]).set(
            {"tags": firestore.ArrayUnion(r["hubAddTags"])}, merge=True)
    for r in history_adds:
        # Purely additive: this records what Attio says happened to the deal and
        # can never remove or overwrite a placement already on the doc.
        db.collection("companies").document(r["key"]).set(
            {"tags": firestore.ArrayUnion(r["historyMissing"])}, merge=True)
    print(f"hub: created {len(creates)}, staged {len(stage_sets)}, "
          f"tagged {len(tag_adds)}, history {len(history_adds)}")
    return {"created": len(creates), "staged": len(stage_sets), "tagged": len(tag_adds),
            "history": len(history_adds), "dryRun": False}


def apply_attio(report, yes=False):
    """Creates a Deal record in Attio for each hub company the rule places and
    Attio is missing. Creates the linked Company record first when there's a
    domain, mirroring pipeline/app.py's find_or_create_company.

    Never patches an EXISTING deal's stage: Attio's stage is where a human files
    a deal, and this script has no way to know why they filed it there. Stage
    disagreements on existing deals are reported for Oscar to action, not
    auto-corrected."""
    from .net import session

    if not config.ATTIO_API_KEY:
        raise RuntimeError("ATTIO_API_KEY not set")
    headers = {"Authorization": f"Bearer {config.ATTIO_API_KEY}",
               "Content-Type": "application/json"}
    creates = [r for r in report["hubOnly"] if r["expectedAttioStage"]]
    print(f"{'DRY RUN -- ' if not yes else ''}attio: {len(creates)} deals to create")
    for r in creates:
        print(f"  create {r['name']:<30} series={r['series'] or '?':<12} stage={r['expectedAttioStage']}")
    if not yes:
        return {"created": 0, "dryRun": True}

    created, failed = 0, []
    for r in creates:
        company_id = None
        if r["domain"]:
            q = session.post(f"{config.ATTIO_BASE}/objects/companies/records/query",
                             json={"filter": {"domains": {"domain": {"$eq": r["domain"]}}}, "limit": 1},
                             headers=headers, timeout=60)
            data = q.json().get("data", []) if q.ok else []
            if data:
                company_id = data[0]["id"]["record_id"]
            else:
                cr = session.post(f"{config.ATTIO_BASE}/objects/companies/records",
                                  json={"data": {"values": {"name": [{"value": r["name"]}],
                                                            "domains": [{"domain": r["domain"]}]}}},
                                  headers=headers, timeout=60)
                if cr.ok:
                    company_id = cr.json().get("data", {}).get("id", {}).get("record_id")
        values = {"name": [{"value": r["name"]}],
                  "stage": [{"status": r["expectedAttioStage"]}],
                  "source": [{"value": "hub sync"}]}
        if company_id:
            values["associated_company"] = [{"target_object": "companies",
                                             "target_record_id": company_id}]
        resp = session.post(f"{config.ATTIO_BASE}/objects/{config.DEALS_OBJECT}/records",
                            json={"data": {"values": values}}, headers=headers, timeout=60)
        if resp.ok:
            created += 1
        else:
            # Series is deliberately NOT sent: it's a single-select and a value
            # Attio has never seen 400s the whole create. Set it by hand (or via
            # the intake path, which has ensure_select_option) on the few deals
            # where it matters.
            failed.append((r["name"], resp.status_code, resp.text[:120]))
        print(f"  DEAL CREATE {r['name']}: {resp.status_code}")
    for name, code, body in failed:
        print(f"  FAILED {name}: {code} {body}")
    return {"created": created, "failed": len(failed), "dryRun": False}


# ── CLI ──────────────────────────────────────────────────────────────────────

def run(attio_csv=None, attio_snapshot=None, hub_snapshot=DEFAULT_HUB_SNAPSHOT,
        refresh=False, out_dir=DEFAULT_OUT_DIR, series_b_mode="dual",
        names_file=None, run_date=None, apply_hub_side=False,
        apply_attio_side=False, yes=False):
    os.makedirs(out_dir, exist_ok=True)
    run_date = run_date or __import__("datetime").date.today().isoformat()

    if refresh:
        rows = dump_attio_snapshot(attio_snapshot or DEFAULT_ATTIO_SNAPSHOT)
        attio = _attio_companies_from_rows(rows)
        hub = hub_companies_from_snapshot(dump_hub_snapshot(hub_snapshot))
    else:
        # Snapshot-first when no source is named: after one --refresh the JSON
        # snapshot is the freshest Attio data on disk, while the committed CSV
        # export can be weeks old. Defaulting to the CSV meant a plain re-run
        # silently reported against stale data and looked like it had worked.
        if not attio_snapshot and not attio_csv and os.path.exists(DEFAULT_ATTIO_SNAPSHOT):
            attio_snapshot = DEFAULT_ATTIO_SNAPSHOT
            print(f"Using {DEFAULT_ATTIO_SNAPSHOT} (pass --attio-csv to read an export instead)")
        if attio_snapshot:
            with open(attio_snapshot, encoding="utf-8") as f:
                attio = _attio_companies_from_rows(json.load(f))
        else:
            attio = attio_companies_from_csv(attio_csv or DEFAULT_ATTIO_CSV)
        with open(hub_snapshot, encoding="utf-8") as f:
            hub = hub_companies_from_snapshot(json.load(f))

    names = read_names_file(names_file) if names_file else None
    report = reconcile(hub, attio, series_b_mode=series_b_mode, names=names)

    md_path = os.path.join(out_dir, f"deal-sync-report-{run_date}.md")
    json_path = os.path.join(out_dir, f"deal-sync-report-{run_date}.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(report, run_date))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({**report, "matchBasis": dict(report["matchBasis"])}, f,
                  indent=2, ensure_ascii=False, default=str)
    csv_paths = write_csvs(report, out_dir, run_date)

    c = report["counts"]
    print(f"\n{c['attioCompanies']} Attio companies vs {c['hubCompanies']} hub companies")
    print(f"  {c['matched']} matched  |  {c['attioOnly']} Attio-only  |  {c['hubOnly']} hub-only")
    print(f"  {c['placementMismatches']} placement disagreements ({c['placementAgreed']} agree)")
    print(f"  {c['aboveBNoTier33']} above B with no Tier 1 (33) backer")
    print(f"  {c['seriesBTop10']} Series B + Top 10 (the series-b-mode population)")
    print(f"\nWrote {md_path}\n      {json_path}")
    for p in csv_paths:
        print(f"      {p}")

    if apply_hub_side:
        apply_hub(report, yes=yes)
    if apply_attio_side:
        apply_attio(report, yes=yes)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--attio-csv", help=f"Attio Deals CSV export (default {DEFAULT_ATTIO_CSV})")
    ap.add_argument("--attio-snapshot", help="Attio deals JSON snapshot (written by --refresh)")
    ap.add_argument("--hub-snapshot", default=DEFAULT_HUB_SNAPSHOT)
    ap.add_argument("--refresh", action="store_true",
                    help="pull both sides live first (needs ATTIO_API_KEY + Firestore creds)")
    ap.add_argument("--out", default=DEFAULT_OUT_DIR)
    ap.add_argument("--series-b-mode", choices=["dual", "radar"], default="dual",
                    help="how a Top 10-backed Series B is placed (see the report's own section)")
    ap.add_argument("--names", help="file of company names that should be in the pipeline on both sides")
    ap.add_argument("--date", help="date stamp for the output filenames (default: today)")
    ap.add_argument("--apply-hub", action="store_true", help="create/tag the missing hub docs")
    ap.add_argument("--apply-attio", action="store_true", help="create the missing Attio deals")
    ap.add_argument("--yes", action="store_true", help="actually write (both --apply-* are dry-run without it)")
    a = ap.parse_args()
    run(attio_csv=a.attio_csv, attio_snapshot=a.attio_snapshot, hub_snapshot=a.hub_snapshot,
        refresh=a.refresh, out_dir=a.out, series_b_mode=a.series_b_mode, names_file=a.names,
        run_date=a.date, apply_hub_side=a.apply_hub, apply_attio_side=a.apply_attio, yes=a.yes)


if __name__ == "__main__":
    sys.exit(main())
