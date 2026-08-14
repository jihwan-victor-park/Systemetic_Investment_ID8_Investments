"""Writes the manually-researched Radar heat scores (Oscar, 2026-08-06: the
research agent's own web search/fetch, NOT Perplexity/Crunchbase/Google
Trends/Apollo -- see docs/RADAR_HEAT_SCORE_RULES.md and
docs/RADAR_HEAT_SCORE_RUN.md) into each company's `radar.marketHeat`,
`radar.clock`, and `radar.schedule` fields -- the table's Predicted Window
and Next Scan columns read `radar.clock.predictedWindowOpen`/
`radar.schedule.nextScanAt` specifically, not `radar.marketHeat`, so those
have to be written too or those columns stay blank for every company this
pass covers.

8 of the 61 companies already have a REAL clock/schedule from an earlier
Python-pipeline backfill (real Apollo headcount, real hazard-linked
cadence) -- this script never overwrites an existing radar.clock/
radar.schedule, only fills them in where they're still missing. `.set(
payload, merge=True)` deep-merges nested maps in Firestore, so
`radar.mandate`/`radar.access`/`radar.hazard` are always left exactly as
they are. Same `db.collection("companies").document(id).set(...,
merge=True)` idiom import_attio_deals_csv.py already uses.

Must run from an environment with real Firestore credentials (Cloud Shell,
not this sandbox -- see docs/RADAR_HEAT_SCORE_RUN.md for why).

Usage:
    python3 -m deal_intelligence.radar_apply_heat_scores [--dry-run]
        [--file deal_intelligence/data/radar-heat-scores-2026-08-06.json]
"""
import argparse
import json

from google.cloud import firestore

from . import config

DEFAULT_FILE = "deal_intelligence/data/radar-heat-scores-2026-08-06.json"


def run(path=DEFAULT_FILE, dry_run=False):
    with open(path) as f:
        entries = json.load(f)
    print(f"{len(entries)} companies in {path}.")

    # Reads happen even under --dry-run (needed to accurately preview which
    # companies already have a real clock/schedule and which don't) --
    # only the final .set() write is skipped. Same Cloud Shell-only
    # requirement either way, so this doesn't change where the script can run.
    db = firestore.Client(project=config.GCP_PROJECT_ID)
    updated, missing, kept_existing_clock = [], [], []

    for entry in entries:
        company_id = entry["id"]
        doc_ref = db.collection("companies").document(company_id)
        snap = doc_ref.get()
        if not snap.exists:
            missing.append(company_id)
            continue
        existing_radar = snap.to_dict().get("radar") or {}

        market_heat = dict(entry["marketHeat"])
        # `source` is dated per-run (assemble_radar_heat_scores.py stamps
        # "manual-web-research-<as-of date>") -- previously hardcoded to
        # 2026-08-06 here regardless of which file was actually passed in,
        # so every later re-run silently mislabeled its own data with the
        # wrong date. Only fall back to a generic label if the entry
        # somehow doesn't carry one.
        market_heat.setdefault("source", "manual-web-research")
        payload = {"marketHeat": market_heat}

        # Only a clock built from REAL Apollo headcount data is protected
        # from being overwritten (2026-08-14 fix -- the guard used to be
        # "does any clock object exist at all", which also silently
        # protected companies whose only "clock" was itself a generic
        # cadence-only fallback estimate with no headcount, identical in
        # substance to what this script is about to write anyway. This
        # module's own docstring always said the intent was narrower: "8
        # of the 61 companies already have a REAL clock/schedule ... real
        # Apollo headcount" -- the code just never actually checked for
        # that.
        existing_clock = existing_radar.get("clock") or {}
        if existing_clock.get("headcountCheckedAt"):
            kept_existing_clock.append(company_id)
        else:
            payload["clock"] = entry["clock"]
            payload["schedule"] = entry["schedule"]

        if not dry_run:
            doc_ref.set({"radar": payload}, merge=True)
        updated.append((company_id, market_heat["score"], market_heat["normalizedScore"]))

    print(f"\n{'DRY RUN -- ' if dry_run else ''}{len(updated)} companies {'would be' if dry_run else ''} updated.")
    for company_id, score, norm in sorted(updated, key=lambda r: (r[2] or 0), reverse=True):
        print(f"  {company_id:<24} score={score:<6} normalizedScore={norm}")
    if kept_existing_clock:
        print(f"\n{len(kept_existing_clock)} already had a real radar.clock/schedule -- left untouched: {kept_existing_clock}")
    if missing:
        print(f"\n{len(missing)} ids not found in Firestore (typo, or company left Radar since research): {missing}")

    return {"updated": len(updated), "missing": missing}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print what would be written, without touching Firestore")
    ap.add_argument("--file", default=DEFAULT_FILE, help="path to the researched heat-scores JSON")
    args = ap.parse_args()
    run(path=args.file, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
