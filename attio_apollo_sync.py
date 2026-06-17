#!/usr/bin/env python3
"""
Weekly Attio → Apollo sync (standalone).

Purpose:
    Keep every contact in your Attio CRM mirrored into Apollo and parked in a
    dormant "holding" sequence. Because they're already in a sequence, Apollo
    will flag them when you build a NEW outreach sequence ("these X contacts
    are already in another sequence") — so you can skip the people you've
    already talked to and never cold-email them twice.

What it does:
    1. Pulls every Person record from Attio (paginated).
    2. Upserts each one into Apollo as a contact (run_dedupe=True, so no dupes).
    3. Enrolls them all in your HOLDING sequence (which must have NO active
       email steps — see note below — so nothing is ever sent).

This script sends ZERO emails. The holding sequence is just a parking lot.

    !!! IMPORTANT !!!
    APOLLO_HOLDING_SEQUENCE_ID must point to a sequence that is empty / paused /
    has no active email steps. Create one in Apollo called something like
    "Attio CRM — Holding (do not send)" and use its ID. It must NOT be your
    real outreach sequence.

Run it:
    export ATTIO_API_KEY=...
    export APOLLO_API_KEY=...
    export APOLLO_HOLDING_SEQUENCE_ID=...
    export APOLLO_MAILBOX_ID=...        # optional
    python attio_apollo_sync.py

Schedule it weekly (example cron, Mondays 8am):
    0 8 * * 1  cd /path/to/project && /usr/bin/python3 attio_apollo_sync.py >> sync.log 2>&1
"""

import os
import sys
import time
import requests

# ── Config ──────────────────────────────────────────────────────────────────
ATTIO_API_KEY              = os.environ.get("ATTIO_API_KEY", "")
APOLLO_API_KEY             = os.environ.get("APOLLO_API_KEY", "")
APOLLO_HOLDING_SEQUENCE_ID = os.environ.get("APOLLO_HOLDING_SEQUENCE_ID", "")
APOLLO_MAILBOX_ID          = os.environ.get("APOLLO_MAILBOX_ID", "")

ATTIO_BASE  = "https://api.attio.com/v2"
APOLLO_BASE = "https://api.apollo.io/api/v1"


def _attio_headers():
    return {"Authorization": f"Bearer {ATTIO_API_KEY}", "Content-Type": "application/json"}


def _apollo_headers():
    return {"X-Api-Key": APOLLO_API_KEY, "Content-Type": "application/json", "Cache-Control": "no-cache"}


# ── Attio: pull all People ────────────────────────────────────────────────────
def pull_attio_people():
    """Page through every Person record in Attio."""
    people, offset = [], 0
    while True:
        resp = requests.post(
            f"{ATTIO_BASE}/objects/people/records/query",
            headers=_attio_headers(),
            json={"limit": 500, "offset": offset},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Attio People query failed {resp.status_code}: {resp.text[:300]}")
        batch = resp.json().get("data", [])
        if not batch:
            break
        people.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
        time.sleep(0.2)
    return people


def extract_contact(record):
    """Map an Attio Person record to the shape Apollo's contact endpoint wants."""
    vals = record.get("values", {})

    emails = vals.get("email_addresses") or []
    email  = emails[0].get("email_address", "") if emails else ""

    name_entries = vals.get("name") or [{}]
    n          = name_entries[0] if name_entries else {}
    first_name = n.get("first_name", "")
    last_name  = n.get("last_name", "")

    def first(field, key="value"):
        items = vals.get(field) or []
        return str(items[0].get(key, "")) if items else ""

    # NOTE: adjust these slugs if your Attio People object uses different ones.
    title    = first("job_title") or first("title") or first("position")
    linkedin = first("linkedin_url") or first("linkedin")

    phones = vals.get("phone_numbers") or []
    phone  = phones[0].get("phone_number", "") if phones else ""

    return {
        "first_name":   first_name,
        "last_name":    last_name,
        "email":        email,
        "title":        title,
        "linkedin_url": linkedin,
        "direct_phone": phone,
    }


# ── Apollo: upsert contact + enroll ───────────────────────────────────────────
def create_apollo_contact(contact):
    """
    Create/upsert a contact in Apollo. run_dedupe=True returns the existing
    contact instead of duplicating. Returns Apollo contact_id or None.
    """
    payload = {
        "first_name":   contact.get("first_name", ""),
        "last_name":    contact.get("last_name", ""),
        "email":        contact.get("email", ""),
        "title":        contact.get("title", ""),
        "linkedin_url": contact.get("linkedin_url", ""),
        "run_dedupe":   True,
    }
    if contact.get("direct_phone"):
        payload["direct_phone"] = contact["direct_phone"]

    try:
        resp = requests.post(f"{APOLLO_BASE}/contacts", headers=_apollo_headers(), json=payload, timeout=15)
        if resp.status_code in (200, 201):
            return resp.json().get("contact", {}).get("id")
        # 422 = duplicate that dedupe didn't merge — look it up by email
        if resp.status_code == 422 and contact.get("email"):
            s = requests.get(
                f"{APOLLO_BASE}/contacts",
                headers=_apollo_headers(),
                params={"q_keywords": contact["email"], "per_page": 1},
                timeout=15,
            )
            if s.status_code == 200:
                rows = s.json().get("contacts", [])
                if rows:
                    return rows[0].get("id")
        print(f"  ! Apollo create failed for {contact.get('email','?')}: {resp.status_code} {resp.text[:150]}")
    except Exception as e:
        print(f"  ! Apollo create error for {contact.get('email','?')}: {e}")
    return None


def enroll_in_holding_sequence(contact_ids):
    """Add contacts to the holding sequence. FREE — no credits, no emails (if sequence is dormant)."""
    if not APOLLO_HOLDING_SEQUENCE_ID:
        return False, "APOLLO_HOLDING_SEQUENCE_ID not set"
    payload = {
        "contact_ids": contact_ids,
        "sequenceActiveInOtherCampaigns":  False,
        "sequenceFinishedInOtherCampaigns": False,
    }
    if APOLLO_MAILBOX_ID:
        payload["mailbox_id"] = APOLLO_MAILBOX_ID
    try:
        resp = requests.post(
            f"{APOLLO_BASE}/emailer_campaigns/{APOLLO_HOLDING_SEQUENCE_ID}/add_contact_ids",
            headers=_apollo_headers(),
            json=payload,
            timeout=30,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, f"{resp.status_code}: {resp.text[:300]}"
    except Exception as e:
        return False, str(e)


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    missing = [v for v in ("ATTIO_API_KEY", "APOLLO_API_KEY") if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}")
        sys.exit(1)

    print("Pulling People from Attio...")
    people = pull_attio_people()
    print(f"  pulled {len(people)} people")

    contacts   = [extract_contact(r) for r in people]
    with_email = [c for c in contacts if c.get("email")]
    print(f"  {len(with_email)} have an email ({len(contacts) - len(with_email)} skipped, no email)")

    print("Upserting into Apollo (run_dedupe=True)...")
    apollo_ids, failed = [], 0
    for c in with_email:
        aid = create_apollo_contact(c)
        if aid:
            apollo_ids.append(aid)
        else:
            failed += 1
        time.sleep(0.12)  # stay under Apollo rate limits
    print(f"  upserted {len(apollo_ids)} ({failed} failed)")

    enrolled = 0
    if apollo_ids and APOLLO_HOLDING_SEQUENCE_ID:
        print(f"Enrolling in holding sequence {APOLLO_HOLDING_SEQUENCE_ID}...")
        ok, info = enroll_in_holding_sequence(apollo_ids)
        if ok:
            enrolled = len(apollo_ids)
            print(f"  enrolled {enrolled} contacts")
        else:
            print(f"  ! enrollment error: {info}")
    elif not APOLLO_HOLDING_SEQUENCE_ID:
        print("  (APOLLO_HOLDING_SEQUENCE_ID not set — contacts upserted but not enrolled)")

    print("\nSUMMARY")
    print(f"  pulled from Attio : {len(people)}")
    print(f"  with email        : {len(with_email)}")
    print(f"  upserted to Apollo: {len(apollo_ids)}")
    print(f"  enrolled (holding): {enrolled}")
    print(f"  failed            : {failed}")
    print("Done.")


if __name__ == "__main__":
    run()
