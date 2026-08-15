"""One-off: write the manual Tier 1 scan (2026-08-14, deal_intelligence/data/
tier1_manual_scan_payload.json) into Firestore, matching the exact
`latestScreen` shape listCompanies() reads (hub-next/src/lib/companies.js's
_mapLatestScreen) plus a same-day `screens/{date}` doc so the Qualified Deals
detail page has something to show instead of "no screens yet".

Stdlib-only REST calls (urllib + `gcloud auth print-access-token` via
subprocess) rather than the google-cloud-firestore Python client, so this
runs in Cloud Shell without a pip install -- same pattern as the read-only
Firestore export earlier in this session.

Run from the repo root, in an environment with `gcloud` authenticated:
    python3 deal_intelligence/data/push_manual_scan_to_firestore.py
Add --dry-run to print what would be written without touching Firestore.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date

PROJECT_ID = "molten-crowbar-498920-q8"
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
HERE = os.path.dirname(__file__)
PAYLOAD_PATH = os.path.join(HERE, "tier1_manual_scan_payload.json")
TODAY = date.today().isoformat()


def _access_token() -> str:
    out = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _v(value):
    """Encode one Python value as a Firestore REST typed Value."""
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_v(x) for x in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {k: _v(v) for k, v in value.items()}}}
    return {"stringValue": str(value)}


def _patch(url: str, fields: dict, update_mask_paths: list, token: str, dry_run: bool):
    body = json.dumps({"fields": {k: _v(v) for k, v in fields.items()}}).encode()
    qs = "&".join(f"updateMask.fieldPaths={p}" for p in update_mask_paths)
    full_url = f"{url}?{qs}"
    if dry_run:
        print(f"[dry-run] PATCH {full_url}\n  {body.decode()[:300]}")
        return
    req = urllib.request.Request(full_url, data=body, method="PATCH", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        urllib.request.urlopen(req).read()
    except urllib.error.HTTPError as e:
        print(f"  FAILED {url}: {e.code} {e.read().decode()[:300]}", file=sys.stderr)
        raise


def _verdict_text(fit_score: float, hard_gate) -> str:
    if hard_gate == "no_ai":
        return "pass — no AI component (mandate gate)"
    if fit_score >= 3.5:
        return "strong go"
    if fit_score >= 3.0:
        return "go / IC review"
    if fit_score > 2.5:
        return "more diligence"
    return "pass"


def main():
    dry_run = "--dry-run" in sys.argv
    with open(PAYLOAD_PATH) as f:
        rows = json.load(f)

    token = None if dry_run else _access_token()
    ok, failed = 0, []
    for i, r in enumerate(rows, 1):
        slug = r["slug"]
        fit_score = r["fitScore"]
        gate = r["gate"]
        round_stage = r.get("roundStage")
        rationale = r.get("rationale", "")
        hard_gate = r.get("hardGate")

        company_url = f"{BASE}/companies/{slug}"
        latest_screen = {
            "date": TODAY,
            "roundStage": round_stage,
            "fitScore": fit_score,
            "gate": gate,
        }
        try:
            _patch(company_url, {"latestScreen": latest_screen}, ["latestScreen"], token, dry_run)

            screen_url = f"{company_url}/screens/{TODAY}"
            screen_doc = {
                "date": TODAY,
                "roundStage": round_stage,
                "fitScore": fit_score,
                "rawScore": fit_score,
                "verdict": _verdict_text(fit_score, hard_gate),
                "gate": gate,
                "hardAutoPassNote": (
                    "Hard auto-pass: no meaningful AI component (mandate gate). [code-enforced]"
                    if hard_gate == "no_ai" else None
                ),
                "dimensions": [],
                "rationale": rationale,
                "confidence": "manual-scan",
                "sources": [],
            }
            _patch(screen_url, screen_doc, list(screen_doc.keys()), token, dry_run)
            ok += 1
        except Exception as exc:  # noqa: BLE001 -- keep the batch alive, report at the end
            failed.append((slug, str(exc)))

        if i % 20 == 0:
            print(f"  {i}/{len(rows)}...")

    print(f"\n{'[dry-run] would write' if dry_run else 'wrote'} {ok}/{len(rows)} companies")
    if failed:
        print(f"FAILED ({len(failed)}):")
        for slug, err in failed:
            print(f"  {slug}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
