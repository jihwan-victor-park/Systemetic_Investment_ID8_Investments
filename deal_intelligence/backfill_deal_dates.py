"""Cloud Run Job entrypoint: one-off backfill of the 'Deal Date' attribute
(Attio Deals object, slug 'deal_date') for the 39 pipeline deals whose Deal
Date was either blank or auto-set to the record's own creation timestamp
(same day/time as Created At -- not a real round date).

Corrected dates come from deal-date-corrections-2026-08-14.json (data/), built
2026-08-14 from Deals - Pipeline (6).csv cross-referenced against PitchBook
company financing histories. Per Oscar's rule (2026-08-14) for which date to
trust:

  - 6 deals already carried a same-day placeholder Deal Date -- kept the
    PitchBook-verified round date already researched for them.
  - Of the 33 deals with a fully blank Deal Date: if the record's Created At
    fell on 2026-06-09 or 2026-06-11 (both known bulk-import timestamps --
    dozens of unrelated deals share the exact same second, so Created At
    carries no real information for these), use the PitchBook date instead.
    Otherwise, Created At is trusted as-is and used directly (even for the
    2026-07-16 batch, which is also a bulk-import timestamp -- Oscar's
    explicit call, not a data quality claim).

Run as `python -m deal_intelligence.backfill_deal_dates` (dry run: prints the
planned change per record, writes nothing) or with `--execute` to actually
PATCH Attio. Not deployed as a schedule -- this is a single-use backfill, run
once via `gcloud run jobs execute`.
"""
import json
import sys
from pathlib import Path

from . import config
from .net import session

CORRECTIONS_FILE = Path(__file__).parent / "data" / "deal-date-corrections-2026-08-14.json"


def _headers():
    return {"Authorization": f"Bearer {config.ATTIO_API_KEY}", "Content-Type": "application/json"}


def _patch_deal_date(record_id: str, date_str: str):
    url = f"{config.ATTIO_BASE}/objects/{config.DEALS_OBJECT}/records/{record_id}"
    body = {"data": {"values": {"deal_date": [{"value": date_str}]}}}
    r = session.patch(url, json=body, headers=_headers(), timeout=60)
    r.raise_for_status()


def main():
    execute = "--execute" in sys.argv[1:]
    if execute and not config.ATTIO_API_KEY:
        print("ATTIO_API_KEY not set -- aborting.", file=sys.stderr)
        sys.exit(1)

    corrections = json.loads(CORRECTIONS_FILE.read_text())
    print(f"Loaded {len(corrections)} corrections from {CORRECTIONS_FILE.name}")
    print(f"Mode: {'EXECUTE (writing to Attio)' if execute else 'DRY RUN (no writes)'}")
    print()

    ok, failed, skipped = 0, 0, 0
    for c in corrections:
        new_date = c["new_deal_date"]
        if not new_date:
            print(f"SKIP  {c['company']:35s} -- no corrected date available")
            skipped += 1
            continue

        print(f"{'WRITE' if execute else 'PLAN '} {c['company']:35s} "
              f"{c['old_deal_date']:>12s} -> {new_date:<12s}  ({c['method']})")

        if execute:
            try:
                _patch_deal_date(c["record_id"], new_date)
                ok += 1
            except Exception as e:
                print(f"      ERROR writing {c['company']}: {e}", file=sys.stderr)
                failed += 1

    print()
    if execute:
        print(f"Done: {ok} written, {failed} failed, {skipped} skipped.")
        if failed:
            sys.exit(1)
    else:
        print(f"Dry run complete: {len(corrections) - skipped} would be written, {skipped} skipped. "
              f"Re-run with --execute to write to Attio.")


if __name__ == "__main__":
    main()
