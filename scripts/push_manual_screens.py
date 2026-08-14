"""Push the manually-scored Stage 1 screens (scripts/manual_stage1_outputs/*.json,
built by manual_stage1_score.py) into production Firestore -- hub only, no Attio
writes, matching the exact companies/{slug} + companies/{slug}/screens/{date}
shape firestore_push.push_company_screen_firestore uses.

Needs real GCP credentials against the production project (Cloud Shell has
these by default).

Usage:
    python3 scripts/push_manual_screens.py             # dry run -- lists only
    python3 scripts/push_manual_screens.py --apply     # actually writes
"""
import argparse
import glob
import json

from google.cloud import firestore

PROJECT_ID = "molten-crowbar-498920-q8"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write; default is dry-run")
    ap.add_argument("--dir", default="scripts/manual_stage1_outputs",
                     help="directory of manual_stage1_score.py outputs to push (default: scripts/manual_stage1_outputs)")
    args = ap.parse_args()

    db = firestore.Client(project=PROJECT_ID)
    files = sorted(glob.glob(f"{args.dir}/*.json"))
    if not files:
        print(f"No files found in {args.dir}/ -- nothing to do.")
        return

    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        slug = data["slug"]
        screen = data["screen"]
        computed = data["_computed"]
        print(f"{slug}: fit_score={computed['fit_score']} tier={computed['quality_tier']} "
              f"gate={computed['gate']} hard_auto_pass={computed['hard_auto_pass']} "
              f"-> companies/{slug}/screens/{screen['date']}")
        if args.apply:
            company_ref = db.collection("companies").document(slug)
            # Mirror deal_intelligence/firestore_push.py's push_company_screen_firestore:
            # denormalize the headline screen fields onto the company doc (so
            # hub-next's listCompanies() Screened column / Run Analysis-vs-Start
            # Stage 2 toggle don't need a screens-subcollection fallback query),
            # and ArrayUnion the "qualified" tag when this screen clears the gate.
            company_payload = dict(data["company"])
            company_payload["latestScreen"] = {
                "date": screen["date"],
                "roundStage": screen["roundStage"],
                "fitScore": computed["fit_score"],
                "gate": computed["gate"],
            }
            if computed["gate"]:
                company_payload["tags"] = firestore.ArrayUnion(["qualified"])
            company_ref.set(company_payload, merge=True)
            company_ref.collection("screens").document(screen["date"]).set(screen, merge=True)

    verb = "Wrote" if args.apply else "Would write"
    print(f"\n{verb} {len(files)} screen(s).")
    if not args.apply:
        print("Dry run only -- re-run with --apply to actually write these to Firestore.")


if __name__ == "__main__":
    main()
