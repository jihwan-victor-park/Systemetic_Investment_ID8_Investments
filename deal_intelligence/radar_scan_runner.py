"""Cloud Run Job entrypoint for Radar's daily scan runner (RADAR_PLAN.md
Part X's Schedule table: "Scan runner | daily job, picks up whatever has
nextScanAt <= today"). Deliberately NOT a Flask route -- a plain script,
run as `python -m deal_intelligence.radar_scan_runner` -- per Part X's own
instruction ("Cloud Run Jobs, not the Flask web service") and the real,
documented request-deadline bug this exact codebase already hit once
(pipeline/app.py's /process endpoint silently dropped every fit_score from
a response once a batch ran past a stale 280s deadline -- see that
endpoint's own comment trail). A daily arithmetic-plus-one-bounded-Apollo-
call job has no request to time out in the first place.

Reads companies directly off Firestore (no Attio re-hit) -- everything
compute_radar_state needs is already denormalized onto the company doc, so
this job's only third-party surface is Apollo (bounded, cheap, and only
called per company when the existing headcount reading is missing or
>30 days stale -- see radar_state.recompute_and_write).

Not deployed by this commit -- see the implementation plan's Cloud Run
Job / Cloud Scheduler section for the (hand-off, not yet run) `gcloud`
commands that actually put this on a schedule.
"""
import sys
from datetime import date

from google.cloud import firestore

from . import config, radar_access, radar_mandate, radar_state


def _due_companies(db, today):
    """companies where (stage == 'radar' OR tags array_contains 'radar') AND
    radar.schedule.nextScanAt <= today -- same additive membership hub-next's
    radar/page.jsx has always used for DISPLAY (`c.stage === 'radar' ||
    c.tags?.includes('radar')`), and the same fix already applied to
    radar_backfill.py's _iter_radar_companies() (2026-07-30, commit
    62ac298): a company carrying just the `radar` TAG (primary stage sits
    elsewhere, Radar is an additive membership) is visible on the hub's
    Radar tab but was never picked up here, so it never scanned and its
    watch-floor streak never advanced. Two queries (stage + array_contains
    tags), merged and deduped by doc id -- Firestore doesn't support ORing
    two different fields in one query without the newer `Or()` composite-
    filter API. Dotted-path filter on a nested map field -- Firestore may
    need a composite index the first time each of these runs in a fresh
    project (it fails with a direct link to create one if so; not something
    creatable from here, same as every other gcloud-side operation in this
    build)."""
    by_stage = (
        db.collection("companies")
        .where("stage", "==", "radar")
        .where("radar.schedule.nextScanAt", "<=", today.isoformat())
    )
    by_tag = (
        db.collection("companies")
        .where("tags", "array_contains", "radar")
        .where("radar.schedule.nextScanAt", "<=", today.isoformat())
    )
    seen = {}
    for doc in by_stage.stream():
        seen[doc.id] = doc
    for doc in by_tag.stream():
        seen.setdefault(doc.id, doc)
    return list(seen.values())


def run(today=None):
    today = today or date.today()
    db = firestore.Client(project=config.GCP_PROJECT_ID)
    due = _due_companies(db, today)
    print(f"[radar-scan-runner] {today.isoformat()}: {len(due)} companies due for a scan.")

    tier1_index = radar_mandate.build_tier1_index(radar_state.list_top_vcs(db))
    partner_index = radar_access.build_partner_index(radar_state.list_partner_vcs(db))

    processed = errors = 0
    for doc in due:
        slug = doc.id
        try:
            data = doc.to_dict()
            fields = radar_state.fields_from_company_doc(data)
            radar_data = radar_state.recompute_and_write(slug, fields, tier1_index, "scan-runner", db=db, today=today, partner_index=partner_index)
            processed += 1
            print(f"[radar-scan-runner]   {slug}: hotness={radar_data.get('hotness')} "
                  f"nextScanAt={(radar_data.get('schedule') or {}).get('nextScanAt')}")
        except Exception as e:
            errors += 1
            print(f"[radar-scan-runner]   {slug}: FAILED -- {e}")

    print(f"[radar-scan-runner] done. {processed} processed, {errors} errors.")
    return {"due": len(due), "processed": processed, "errors": errors}


if __name__ == "__main__":
    result = run()
    sys.exit(1 if result["errors"] else 0)
