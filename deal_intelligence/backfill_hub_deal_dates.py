"""One-off backfill of Firestore's companies/{slug}.roundDate field -- the
same field hub-next's own "edit deal date" feature writes
(updateCompanyRoundDate in hub-next/src/lib/companies.js) and the same field
every reader in the hub displays from (CompanyDetailPage's "closed <date>",
companyStageColumns' Deal Date column, Radar's capital-clock input). This is
the direct, no-Attio-round-trip version of the correction in
backfill_deal_dates.py -- run this one to fix what the hub shows; run that
one separately if/when Attio's own copy should also be reconciled (Oscar,
2026-08-14: "i dont care about attio right now").

Corrected dates: see backfill_deal_dates.py's module docstring for the full
derivation (PitchBook financing history + Created At, per Oscar's 2026-08-14
rule). Both scripts read the same deal-date-corrections-2026-08-14.json.

Slug is computed the same way fit_note.company_id() does -- first label of
the domain, lowercased, non-alnum runs collapsed to '-'; falls back to a
slug of the company name if there's no domain.

Run as `python -m deal_intelligence.backfill_hub_deal_dates` (dry run: prints
the planned change per company, writes nothing) or with `--execute` to
actually write to Firestore. Needs real GCP credentials (Cloud Shell's
gcloud ADC, or a Cloud Run service account) -- not available in a bare
sandbox, which is why this can't run itself from here.
"""
import json
import re
import sys
from pathlib import Path

from . import config

CORRECTIONS_FILE = Path(__file__).parent / "data" / "deal-date-corrections-2026-08-14.json"


def _slug_for(domain: str, company: str) -> str:
    d = (domain or "").strip()
    d = re.sub(r"^https?://", "", d, flags=re.I)
    d = re.sub(r"^www\.", "", d, flags=re.I).rstrip("/").lower()
    if d:
        return re.sub(r"[^a-z0-9]+", "-", d.split(".")[0]).strip("-")
    return re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")


def main():
    execute = "--execute" in sys.argv[1:]
    corrections = json.loads(CORRECTIONS_FILE.read_text())
    print(f"Loaded {len(corrections)} corrections")
    print(f"Mode: {'EXECUTE (writing to Firestore)' if execute else 'DRY RUN (no writes)'}")
    print()

    db = None
    if execute:
        from google.cloud import firestore
        db = firestore.Client(project=config.GCP_PROJECT_ID)

    ok, missing, skipped = 0, 0, 0
    for c in corrections:
        new_date = c["new_deal_date"]
        if not new_date:
            print(f"SKIP  {c['company']:35s} -- no corrected date available")
            skipped += 1
            continue

        slug = _slug_for(c["domain"], c["company"])
        print(f"{'WRITE' if execute else 'PLAN '} {c['company']:35s} slug={slug:26s} "
              f"{c['old_deal_date']:>12s} -> {new_date:<12s}")

        if execute:
            ref = db.collection("companies").document(slug)
            snap = ref.get()
            if not snap.exists:
                print(f"      MISSING: no Firestore doc at companies/{slug}", file=sys.stderr)
                missing += 1
                continue
            ref.set({"roundDate": new_date}, merge=True)
            ok += 1

    print()
    if execute:
        print(f"Done: {ok} written, {missing} missing (no matching Firestore doc), {skipped} skipped.")
        if missing:
            print("Missing slugs need a manual look -- either the domain-derived slug is "
                  "wrong or the company isn't in Firestore yet.")
    else:
        print(f"Dry run complete: {len(corrections) - skipped} would be written. "
              f"Re-run with --execute to write to Firestore.")


if __name__ == "__main__":
    main()
