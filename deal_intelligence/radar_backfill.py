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

from . import config, radar_mandate, radar_signal_series, radar_state


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
    # Fetched once and reused across every company, same convention as
    # tier1_index -- avoids a radarConfig read per company.
    watch_floor = radar_state._get_watch_floor(db)

    results = []
    for doc in docs:
        data = doc.to_dict()
        slug = doc.id
        fields = radar_state.fields_from_company_doc(data)
        existing_radar = data.get("radar") or {}
        if dry_run:
            # Mirrors compute_radar_state's own logic without writing --
            # calls it directly (pure, no I/O) using whatever headcount/
            # job-signal data is ALREADY on the company doc, so --dry-run
            # never makes a fresh Apollo or job-board call and stays a
            # genuine read-only preview -- including of the real hazard
            # numbers, not just the mandate pass/fail split.
            existing_clock = existing_radar.get("clock") or {}
            existing_schedule = existing_radar.get("schedule") or {}
            headcount_series = radar_signal_series.read_series(db, slug, "headcount")
            headcount_growth = radar_signal_series.growth_rate(headcount_series) if headcount_series else None
            radar_data = radar_state.compute_radar_state(
                fields, tier1_index,
                existing_clock.get("headcount"), existing_clock.get("headcountCheckedAt"),
                radar_state._parse_date(existing_schedule.get("lastScanAt")),
                existing_schedule.get("scanCount", 0), advance_scan=False,
                headcount_growth=headcount_growth, job_signals=existing_radar.get("jobSignals"),
                low_score_streak=existing_radar.get("lowScoreStreak", 0), watch_floor=watch_floor,
            )
        else:
            radar_data = radar_state.recompute_and_write(slug, fields, tier1_index, "backfill", db=db, watch_floor=watch_floor)
        mandate = radar_data["mandate"]
        hazard = radar_data.get("hazard") or {}
        results.append((
            slug, fields["name"], mandate["pass"], mandate.get("failReason"),
            hazard.get("heatPoints"), hazard.get("familiesActive"),
        ))

    passed = [r for r in results if r[2]]
    failed = [r for r in results if not r[2]]
    print(f"\n{'DRY RUN -- ' if dry_run else ''}{len(passed)} pass, {len(failed)} fail the mandate screen.\n")
    for slug, name, ok, reason, heat_points, families in results:
        status = "PASS" if ok else f"FAIL  ({reason})"
        heat_desc = f"heat={heat_points} families={','.join(families) if families else 'none'}" if ok else ""
        print(f"  {status:<45} {heat_desc:<38} {name or slug}")

    return {"total": len(docs), "passed": len(passed), "failed": len(failed)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print the mandate pass/fail split without writing anything")
    ap.add_argument("--limit", type=int, default=None, help="only process the first N companies (for a quick check)")
    args = ap.parse_args()
    run(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
