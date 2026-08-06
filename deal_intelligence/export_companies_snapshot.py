"""Dumps the full `companies` collection to a JSON file, so a real snapshot
of production data can be committed/shared instead of working blind off a
single CSV export (Oscar, 2026-08-06: "I want to download from firebase so
that you can double check and create the queries... to put all the
information").

Read-only -- never writes anything to Firestore. Run from Cloud Shell (this
sandbox has no production credentials):

    python3 -m deal_intelligence.export_companies_snapshot

Writes `deal_intelligence/data/companies-snapshot.json` -- an array of
`{id, ...every field on the doc}`, Firestore Timestamps converted to plain
ISO strings so the file is normal, readable JSON (no special object types
that only make sense inside a Firestore SDK). Once written, `git add` +
commit + push it the same way the Deals CSV was committed
(deal_intelligence/data/attio-deals-export.csv) -- same convention, input
data alongside the code that reads it, so a `git pull` picks it up with no
manual upload step.
"""
import json
import sys
from datetime import datetime, date

from google.cloud import firestore

from . import config


def _jsonable(value):
    """Recursively converts Firestore-specific types (Timestamp/DatetimeWithNanoseconds,
    DocumentReference, GeoPoint) into plain JSON-safe values -- a raw
    `doc.to_dict()` has real objects in it that `json.dumps` can't serialize
    on its own."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "path"):  # DocumentReference
        return value.path
    if hasattr(value, "latitude") and hasattr(value, "longitude"):  # GeoPoint
        return {"lat": value.latitude, "lng": value.longitude}
    return value


def run():
    db = firestore.Client(project=config.GCP_PROJECT_ID)
    docs = list(db.collection("companies").stream())
    print(f"{len(docs)} companies found.")

    snapshot = [{"id": doc.id, **_jsonable(doc.to_dict())} for doc in docs]

    out_path = "deal_intelligence/data/companies-snapshot.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)

    stages = {}
    for c in snapshot:
        stages[c.get("stage")] = stages.get(c.get("stage"), 0) + 1
    radar_tagged = sum(1 for c in snapshot if "radar" in (c.get("tags") or []))
    print(f"Wrote {out_path}")
    print(f"By stage: {stages}")
    print(f"Additionally tagged 'radar' (on top of whatever stage): {radar_tagged}")
    print(f"Total on the Radar tab (stage=='radar' OR tags includes 'radar'): "
          f"{stages.get('radar', 0) + sum(1 for c in snapshot if c.get('stage') != 'radar' and 'radar' in (c.get('tags') or []))}")


if __name__ == "__main__":
    sys.exit(run())
