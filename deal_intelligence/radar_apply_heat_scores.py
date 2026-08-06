"""Writes the manually-researched Radar heat scores (Oscar, 2026-08-06: the
research agent's own web search/fetch, NOT Perplexity/Crunchbase/Google
Trends/Apollo -- see docs/RADAR_HEAT_SCORE_RULES.md and
docs/RADAR_HEAT_SCORE_RUN.md) into each company's `radar.marketHeat` field.

Only touches `radar.marketHeat` -- `.set(payload, merge=True)` deep-merges
nested maps in Firestore, so `radar.clock`/`radar.mandate`/`radar.access`/
`radar.schedule`/`radar.hazard` are left exactly as they are. Same
`db.collection("companies").document(id).set(..., merge=True)` idiom
import_attio_deals_csv.py already uses.

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

    db = None if dry_run else firestore.Client(project=config.GCP_PROJECT_ID)
    updated, missing = [], []

    for entry in entries:
        company_id = entry["id"]
        # Already in radar_market_heat.compute()'s own return shape (signals
        # with weight/contribution baked in via that module's _entry(),
        # timingUrgencyMultiplier/monthsUntilWindow applied) -- just pass it
        # through, plus a provenance tag so a real Perplexity-backed re-scan
        # later doesn't get confused about where these numbers came from.
        market_heat = {k: v for k, v in entry.items() if k != "id"}
        market_heat["source"] = "manual-web-research-2026-08-06"
        if dry_run:
            updated.append((company_id, market_heat["score"], market_heat["normalizedScore"]))
            continue

        doc_ref = db.collection("companies").document(company_id)
        if not doc_ref.get().exists:
            missing.append(company_id)
            continue
        doc_ref.set({"radar": {"marketHeat": market_heat}}, merge=True)
        updated.append((company_id, market_heat["score"], market_heat["normalizedScore"]))

    print(f"\n{'DRY RUN -- ' if dry_run else ''}{len(updated)} companies {'would be' if dry_run else ''} updated.")
    for company_id, score, norm in sorted(updated, key=lambda r: (r[2] or 0), reverse=True):
        print(f"  {company_id:<24} score={score:<6} normalizedScore={norm}")
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
