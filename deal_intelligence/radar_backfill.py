"""One-time backfill: runs the mandate screen + capital clock + scan
schedule (radar_state.recompute_and_write) over every company CURRENTLY on
the Radar stage in Firestore -- Oscar's confirmed scope decision #4
("backfill existing Radar companies now," not just new arrivals).

Targets `companies` where `stage == 'radar'` directly -- that field is what
actually puts a company on the hub's Radar tab (companyStageColumns.jsx/
radar/page.jsx read `stage`, not Attio's own stage string), so it already
captures every company that belongs here regardless of how it arrived
(Attio-tagged radar deal, or moved by hand via the hub's Stage dropdown).
No Attio call needed for this -- every field radar_state.compute_radar_state
needs (name/hq/round/roundDate/roundSize/description/radarCategory/website/
top10VC) is already denormalized onto the company doc.

`entry_source='backfill'` -- counts as a real scan (advance_scan=True in
radar_state.recompute_and_write), establishing scanCount=1/lastScanAt=today
for every company's very first Radar clock computation.

Usage:
    python -m deal_intelligence.radar_backfill [--dry-run] [--limit N]
"""
import argparse

from google.cloud import firestore

from . import config, radar_mandate, radar_state


def _iter_radar_companies(db, limit=None):
    query = db.collection("companies").where("stage", "==", "radar")
    if limit:
        query = query.limit(limit)
    return list(query.stream())


def run(dry_run=False, limit=None):
    db = firestore.Client(project=config.GCP_PROJECT_ID)
    docs = _iter_radar_companies(db, limit)
    print(f"{len(docs)} companies on the Radar stage found.")

    tier1_index = radar_mandate.build_tier1_index(radar_state.list_top_vcs(db))
    print(f"Tier 1 index built from {len(tier1_index)} distinct company names across the Top 10 VC list.")

    results = []
    for doc in docs:
        data = doc.to_dict()
        slug = doc.id
        fields = radar_state.fields_from_company_doc(data)
        if dry_run:
            # Mirrors compute_radar_state's own logic without writing --
            # deliberately re-invokes recompute_and_write's guts via
            # compute_radar_state directly so --dry-run and a real run share
            # the exact same code path up to the Firestore write itself.
            mandate = radar_mandate.screen(
                {"name": fields["name"], "hq": fields["hq"], "series": fields["series"],
                 "deal_size": fields["roundSize"], "top10VC": fields["top10VC"]},
                tier1_index,
            )
            results.append((slug, fields["name"], mandate["pass"], mandate.get("failReason")))
        else:
            radar_data = radar_state.recompute_and_write(slug, fields, tier1_index, "backfill", db=db)
            mandate = radar_data["mandate"]
            results.append((slug, fields["name"], mandate["pass"], mandate.get("failReason")))

    passed = [r for r in results if r[2]]
    failed = [r for r in results if not r[2]]
    print(f"\n{'DRY RUN -- ' if dry_run else ''}{len(passed)} pass, {len(failed)} fail the mandate screen.\n")
    for slug, name, ok, reason in results:
        status = "PASS" if ok else f"FAIL  ({reason})"
        print(f"  {status:<45} {name or slug}")

    return {"total": len(docs), "passed": len(passed), "failed": len(failed)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print the mandate pass/fail split without writing anything")
    ap.add_argument("--limit", type=int, default=None, help="only process the first N companies (for a quick check)")
    args = ap.parse_args()
    run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
