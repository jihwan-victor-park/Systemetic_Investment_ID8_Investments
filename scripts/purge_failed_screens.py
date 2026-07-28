"""One-off cleanup for the Perplexity-401 incident: delete Stage 1 "scoring
failed" screen docs from production Firestore so the real screen underneath
(an earlier dated doc for the same company, if one exists) becomes the
"latest" one again -- hub-next always picks the max-date doc in
companies/{slug}/screens, with no success/failure filtering, so removing the
failed doc is enough; nothing needs to be rewritten.

Companies with NO real screen underneath (the failed run was their first
ever) just end up with no screens at all -- back to "not yet screened,"
ready for a clean re-run once the Perplexity key is fixed.

Needs real GCP credentials against the production project (Cloud Shell has
these by default via the project's service account / your logged-in user).

Usage:
    python3 scripts/purge_failed_screens.py            # dry run -- lists only
    python3 scripts/purge_failed_screens.py --apply    # actually deletes
"""
import argparse

from google.cloud import firestore

PROJECT_ID = "molten-crowbar-498920-q8"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete; default is dry-run")
    args = ap.parse_args()

    db = firestore.Client(project=PROJECT_ID)
    hits = []
    for company in db.collection("companies").stream():
        screens = list(company.reference.collection("screens").order_by("date").stream())
        real_left = sum(1 for s in screens if "scoring failed" not in (s.to_dict().get("rationale") or "").lower())
        for s in screens:
            data = s.to_dict()
            if "scoring failed" in (data.get("rationale") or "").lower():
                hits.append((company.id, s.id, real_left > 0))
                if args.apply:
                    s.reference.delete()

    if not hits:
        print("No failed screens found -- nothing to do.")
        return

    verb = "Deleted" if args.apply else "Would delete"
    print(f"{verb} {len(hits)} failed screen doc(s):\n")
    for slug, screen_id, has_real_prior in hits:
        note = "-> real prior screen resurfaces as latest" if has_real_prior else "-> no prior screen, goes back to unscreened"
        print(f"  {slug}/screens/{screen_id}  {note}")

    if not args.apply:
        print("\nDry run only -- re-run with --apply to actually delete these.")


if __name__ == "__main__":
    main()
