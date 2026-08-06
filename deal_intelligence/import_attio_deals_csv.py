"""Reconciles an Attio "Deals" CSV export against the hub's Firestore company
docs (Oscar, 2026-08-05: match up the pipeline/passed/access picture, pull in
each company's real investor list, and stamp which of the Top 10 / Tier 1
(33) firms actually invested).

Run as `python -m deal_intelligence.import_attio_deals_csv <csv_path>
[--dry-run]` -- same CLI shape as radar_backfill.py. ALWAYS run --dry-run
first and read the summary before a real write; this touches production
Firestore at scale (hundreds of companies in one run).

What this does, per company (grouped from possibly-several CSV rows -- see
`group_by_company`):

- `investors`: every unique investor name off the CSV's Lead/New/Investors
  columns, refreshed unconditionally (external-truth field, same convention
  as `investorDomains`/`description` in firestore_push.push_company_from_attio).
- `investorDomains`: the CSV's `Investors > Domains` column (when present --
  see below), refreshed unconditionally, same field/convention
  `push_company_from_attio` already writes -- this is what already drives
  companyIndex.js's domain-based Partner VC / Tier 1 portfolio matching on
  every page render, so this import feeds that existing machinery directly
  rather than duplicating it.
- `access`: Attio's own "Access" field, normalized to `"access"`/`"no_access"`
  (Oscar, 2026-08-06: "deals qualified/pipeline (the ones we get access to)"
  -- a real dimension for the summary-statistics page, previously never
  captured anywhere in the hub). Sparse in this export (mostly blank) --
  no field written when blank, same missing-not-a-fabricated-value
  convention as everything else here.
- `top10Investors` / `tier1_33Investors`: which of `tier1_firms.TOP10` /
  `tier1_firms.TIER1_33` are on that investor list, via the existing
  `match_top10`/`match_tier1_33` matchers (match_tier1_33 had ZERO callers
  anywhere in this codebase before this script -- this is the first thing
  that actually uses it). Domain+name matching when the CSV has an
  `Investors > Domains` column (same precision as the PitchBook intake
  path); falls back to name-only against `tier1_firms.match_top10` when it
  doesn't -- stated in the summary output either way, not hidden.
- `passed` + `pipeline` tags: both added via ArrayUnion (additive, same
  mechanism radar_state.py already uses for the `radar` tag) when the
  company's CURRENT (most recent by Deal Date) row's stage is "Passed" --
  named to match Attio's own stage label exactly (Oscar, 2026-08-05: "I
  want it to be called passed"), not translated to a different word in the
  hub. `pipeline` rides along automatically (Oscar, 2026-08-06: "make sure
  the lists of the passed deals are all tagged as both pipeline and passed
  [because] we had access to them" -- passing on a deal means it was
  actually evaluated). Never touches `stage` or any other existing tag on
  an already-tracked company -- a company that was Passed once and later
  moved back to Pipeline reads as Pipeline today, not Passed (several rows
  in this export show exactly that kind of stage history in "Deal stage"
  Previous Values). Because these are additive, many companies will carry
  BOTH their working stage AND these tags at once -- a real case to account
  for when building anything that counts deals by stage (e.g. a
  summary-statistics view), not an edge case to special-case away.
- Companies not already in Firestore get created (Oscar's explicit call,
  2026-08-05) -- `stage` from `config.ATTIO_STAGE_MAP`, same fallback-to-
  'new' rule `push_company_from_attio` already uses for an unmapped stage.
- A company with MULTIPLE CSV rows (different series/rounds -- e.g. this
  export's two separate "Ollama" records) gets one primary doc (the most
  recent row) plus an additional-round doc per older row, `${companyKey}--
  ${roundSlug}`, mirroring hub-next's own createAdditionalRound() id shape
  exactly -- never collapsed/overwritten into one row losing the round
  history.
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from datetime import date

from google.cloud import firestore

from . import config, tier1_firms
from .fit_note import normalize_domain, slugify

PASSED_TAG = "passed"       # the hub tag this script writes (ArrayUnion onto `tags`)
PASSED_STAGE = "passed"     # the Attio "Deal stage" value that triggers it

_db = None


def _firestore():
    global _db
    if _db is None:
        _db = firestore.Client(project=config.GCP_PROJECT_ID)
    return _db


def company_key_of(domain, name):
    """Mirrors deal_intelligence/fit_note.py's company_id() exactly (domain-
    first, name-fallback slug) -- so a company already in Firestore via the
    normal Attio-import path resolves to the SAME doc id here, and this
    import updates it rather than creating a duplicate."""
    d = normalize_domain(domain)
    if d:
        return re.sub(r"[^a-z0-9]+", "-", d.split(".")[0].lower()).strip("-")
    return slugify(name)


def parse_comma_list(cell):
    """One CSV cell of comma-separated values (investor names OR domains) ->
    deduped list. Uses csv.reader on the single cell rather than a naive
    .split(',') so the one embedded-quote edge case this export actually has
    (a firm name that itself contains a comma, quoted by Attio's own export
    -- '\"Atreides Management,\",Index Ventures,TCV') parses as 2 items, not
    4. Domains and names share this same parser -- both are plain
    comma-separated lists in this export, no per-item quoting differences."""
    if not cell:
        return []
    items = next(csv.reader([cell]), [])
    return sorted({i.strip() for i in items if i.strip()})


def read_rows(csv_path):
    """Yields one plain dict per CSV row, just the fields this script needs.
    `investor_domains` is [] on an export without an 'Investors > Domains'
    column (the original CSV (11) shape) -- match_top10 degrades to
    name-only matching in that case, same as it always has."""
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = (row.get("Associated company > Domains") or "").split(",")[0].strip()
            investor_names = (
                parse_comma_list(row.get("Lead Investors > Name"))
                + parse_comma_list(row.get("New Investors > Name"))
                + parse_comma_list(row.get("Investors > Name"))
            )
            yield {
                "name": (row.get("Record") or "").strip(),
                "domain": domain,
                "stage": (row.get("Deal stage") or "").strip(),
                "stage_changed_at": (row.get('"Deal stage" Changed At') or "").strip(),
                "deal_date": (row.get("Deal Date") or "").strip(),
                "series": (row.get("Series") or "").strip(),
                "description": (row.get("Associated company > Description") or "").strip(),
                "investor_names": sorted(set(investor_names)),
                "investor_domains": parse_comma_list(row.get("Investors > Domains")),
                "access": (row.get("Access") or "").strip(),
            }


def group_by_company(rows):
    """Groups CSV rows by resolved company key -- a pure function over
    already-parsed row dicts, no I/O, so it's unit-testable with fabricated
    fixtures. Returns {company_key: [rows...]}, insertion order preserved
    per group (not sorted -- see authoritative_row for the "current state"
    pick)."""
    groups = defaultdict(list)
    for row in rows:
        key = company_key_of(row["domain"], row["name"])
        if key:
            groups[key].append(row)
    return dict(groups)


def authoritative_row(rows):
    """The row that determines a company's CURRENT stage/passed status --
    latest by Deal Date, falling back to "Deal stage" Changed At when Deal
    Date is missing or ties (a deal that changed stage without a new round
    closing still needs a tiebreak). This is what makes a company that was
    Passed once and later moved back to Pipeline read as Pipeline today, not
    Passed -- exactly what this export's own "Deal stage" Previous Values
    column shows happening for several companies (Etched, Atoms, Ollama)."""
    return max(rows, key=lambda r: (r["deal_date"] or "", r["stage_changed_at"] or ""))


def _round_slug(series):
    return slugify(series) if series else "round"


def process_group(company_key, rows, db, dry_run):
    """Writes (or, in --dry-run, computes without writing) one company
    group's investors/top10Investors/tier1_33Investors/passed-tag, plus an
    additional-round doc per non-authoritative row. Returns a summary dict
    for the run-level tally."""
    auth = authoritative_row(rows)
    other_rows = [r for r in rows if r is not auth]

    all_investor_names = sorted({n for r in rows for n in r["investor_names"]})
    all_investor_domains = sorted({d for r in rows for d in r["investor_domains"]})
    top10 = tier1_firms.match_top10(investor_domains=all_investor_domains, investor_names=all_investor_names)
    tier1_33 = tier1_firms.match_tier1_33(investor_names=all_investor_names)
    is_passed = auth["stage"].strip().lower() == PASSED_STAGE
    # Attio's own "Access" field (Oscar, 2026-08-06: "deals qualified/pipeline
    # (the ones we get access to)" -- a real dimension for the stats page,
    # not previously captured anywhere in the hub). Sparse in this export
    # (mostly blank) -- None (no field written) when blank, same
    # missing-not-a-fabricated-value convention as everything else here.
    access_raw = auth["access"].strip().lower()
    access = {"access": "access", "no access": "no_access"}.get(access_raw)

    company_ref = db.collection("companies").document(company_key)
    existing_snap = company_ref.get()
    is_new = not existing_snap.exists

    payload = {}
    if all_investor_names:
        payload["investors"] = all_investor_names
    if all_investor_domains:
        # Same field companyIndex.js's domain-based Partner VC / Tier 1
        # portfolio matching already reads -- feeds that existing live
        # machinery directly, same refresh-every-push convention
        # push_company_from_attio already uses for this exact field.
        payload["investorDomains"] = all_investor_domains
    if top10:
        payload["top10Investors"] = top10
    if tier1_33:
        payload["tier1_33Investors"] = tier1_33
    if access:
        payload["access"] = access
    if is_passed:
        # Every Passed company also gets tagged 'pipeline' (Oscar,
        # 2026-08-06: "make sure the lists of the passed deals are all
        # tagged as both pipeline and passed [because] we had access to
        # them") -- passing on a deal means it was actually evaluated, not
        # just glanced at, so it belongs in Pipeline's own history
        # regardless of whatever its Attio stage happened to be. This is
        # also what makes the Pipeline view's "Show passed deals" toggle
        # (DealsListSection.jsx) the one place Passed companies are
        # guaranteed to surface.
        payload["tags"] = firestore.ArrayUnion([PASSED_TAG, "pipeline"])
    if is_new:
        payload["name"] = auth["name"]
        payload["website"] = normalize_domain(auth["domain"]) or None
        payload["round"] = auth["series"] or None
        if auth["description"]:
            payload["description"] = auth["description"]
        payload["stage"] = config.ATTIO_STAGE_MAP.get(auth["stage"].strip().lower(), "new")
        # Explicit None, not an absent key -- hub-next's listCompanies()
        # (lib/companies.js) falls back to a wasted extra Firestore read per
        # company whenever this field is genuinely UNDEFINED (vs. explicitly
        # null), to check a screens subcollection that doesn't exist yet for
        # a brand-new company. Same fix as scripts/backfill-latest-screen.mjs,
        # applied here so a freshly-imported company never opens that gap in
        # the first place.
        payload["latestScreen"] = None
        payload["origin"] = {
            "source": "attio-deals-csv-import",
            "importedAt": firestore.SERVER_TIMESTAMP,
        }
    elif auth["description"]:
        # Same "refresh on every push, new or existing alike" rule
        # push_company_from_attio already uses for description.
        payload["description"] = auth["description"]

    additional_rounds = []
    auth_round_slug = _round_slug(auth["series"])
    for r in other_rows:
        round_slug = _round_slug(r["series"])
        if round_slug == auth_round_slug:
            continue  # same round as the primary row, nothing new to record
        round_doc_id = f"{company_key}--{round_slug}"
        additional_rounds.append((round_doc_id, r))

    if not dry_run:
        company_ref.set(payload, merge=True)
        if additional_rounds and not (existing_snap.exists and existing_snap.to_dict().get("companyKey")):
            company_ref.set({"companyKey": company_key}, merge=True)
        for round_doc_id, r in additional_rounds:
            round_ref = db.collection("companies").document(round_doc_id)
            if round_ref.get().exists:
                continue  # idempotent re-run: already recorded
            round_ref.set({
                "name": auth["name"],
                "website": normalize_domain(r["domain"]) or None,
                "stage": config.ATTIO_STAGE_MAP.get(r["stage"].strip().lower(), "new"),
                "round": r["series"] or None,
                "companyKey": company_key,
                "latestScreen": None,  # see the same field's comment above -- avoids listCompanies()'s N+1 fallback
                "origin": {
                    "source": "attio-deals-csv-import-additional-round",
                    "importedAt": firestore.SERVER_TIMESTAMP,
                },
            })

    return {
        "companyKey": company_key,
        "name": auth["name"],
        "isNew": is_new,
        "isPassed": is_passed,
        "top10": top10,
        "tier1_33": tier1_33,
        "additionalRounds": len(additional_rounds),
    }


def run(csv_path, dry_run=False):
    rows = list(read_rows(csv_path))
    groups = group_by_company(rows)
    db = _firestore()

    results = [process_group(key, group_rows, db, dry_run) for key, group_rows in groups.items()]

    created = [r for r in results if r["isNew"]]
    existing = [r for r in results if not r["isNew"]]
    passed = [r for r in results if r["isPassed"]]
    top10_matched = [r for r in results if r["top10"]]
    tier1_33_matched = [r for r in results if r["tier1_33"]]
    total_additional_rounds = sum(r["additionalRounds"] for r in results)

    print(f"\n{'DRY RUN -- ' if dry_run else ''}{len(rows)} CSV rows -> {len(groups)} companies")
    print(f"  {len(created)} new company docs {'would be ' if dry_run else ''}created")
    print(f"  {len(existing)} existing companies matched and updated")
    print(f"  {len(passed)} tagged 'passed' (current stage = Passed)")
    print(f"  {len(top10_matched)} companies with a Top 10 investor match")
    print(f"  {len(tier1_33_matched)} companies with a Tier 1 (33) investor match")
    print(f"  {total_additional_rounds} additional-round docs {'would be ' if dry_run else ''}written")
    if created:
        print("\n  New companies:")
        for r in created:
            print(f"    {r['companyKey']:<30} {r['name']}")

    return {
        "rows": len(rows), "companies": len(groups), "created": len(created),
        "existing": len(existing), "passed": len(passed),
        "top10Matched": len(top10_matched), "tier1_33Matched": len(tier1_33_matched),
        "additionalRounds": total_additional_rounds,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv_path", help="path to the Attio Deals CSV export")
    ap.add_argument("--dry-run", action="store_true", help="print the summary without writing anything")
    args = ap.parse_args()
    run(args.csv_path, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
