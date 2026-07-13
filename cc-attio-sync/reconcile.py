"""
Attio List -> Constant Contact list reconciliation.

Attio has no "record removed from list" automation trigger (confirmed against
Attio's own docs/support -- only "record added to list", "list entry updated",
and a manual "list entry command" exist), so removals can't be webhook-driven
the way adds are in main.py. This periodically re-reads each configured
Attio List's current membership and removes anyone from the matching
Constant Contact list who's no longer in it.

Never deletes the CC contact or touches their other list memberships -- only
removes the one list membership that fell out of sync, via a read-modify-write
on the contact (CC v3's PUT replaces the whole resource, so we always GET
fresh immediately before mutating, and only touch the list_memberships key on
that exact object -- every other field goes back byte-for-byte as CC returned
it, so this doesn't depend on knowing the full contact schema).
"""
import os

import requests

ATTIO_BASE = "https://api.attio.com/v2"


def _attio_headers():
    return {"Authorization": f"Bearer {os.environ['ATTIO_API_KEY']}",
            "Content-Type": "application/json"}


def attio_list_emails(list_id):
    """All current member emails of an Attio List, lowercased. Requires the
    ATTIO_API_KEY to have list_entry:read + list_configuration:read scopes."""
    emails = set()
    offset = 0
    while True:
        r = requests.post(
            f"{ATTIO_BASE}/lists/{list_id}/entries/query",
            json={"filter": {}, "limit": 500, "offset": offset},
            headers=_attio_headers(), timeout=30,
        )
        r.raise_for_status()
        entries = r.json().get("data", [])
        for entry in entries:
            for val in entry.get("entry_values", {}).get("email_addresses", []):
                addr = val.get("email_address")
                if addr:
                    emails.add(addr.lower())
        if len(entries) < 500:
            break
        offset += 500
    return emails


def cc_list_contacts(cc_api, access_token, cc_list_id):
    """All current CC contacts on a list: {email.lower(): contact_id}."""
    contacts = {}
    headers = {"Authorization": f"Bearer {access_token}"}
    url, params = f"{cc_api}/contacts", {"lists": cc_list_id, "limit": 500}
    while url:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        body = r.json()
        for c in body.get("contacts", []):
            email_field = c.get("email_address")
            addr = email_field.get("address") if isinstance(email_field, dict) else email_field
            cid = c.get("contact_id")
            if addr and cid:
                contacts[addr.lower()] = cid
        next_href = ((body.get("_links") or {}).get("next") or {}).get("href")
        url = f"{cc_api.rsplit('/v3', 1)[0]}{next_href}" if next_href else None
        params = None  # next_href already carries the query string
    return contacts


def remove_from_cc_list(cc_api, access_token, contact_id, cc_list_id):
    """Read-modify-write: GET the contact fresh, drop cc_list_id from its
    list_memberships, PUT the SAME object back with only that key changed.
    Returns True if a removal actually happened, False if already absent."""
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    r = requests.get(f"{cc_api}/contacts/{contact_id}", headers=headers, timeout=30)
    r.raise_for_status()
    contact = r.json()
    memberships = contact.get("list_memberships", [])
    if cc_list_id not in memberships:
        return False
    contact["list_memberships"] = [l for l in memberships if l != cc_list_id]
    put = requests.put(f"{cc_api}/contacts/{contact_id}", json=contact, headers=headers, timeout=30)
    put.raise_for_status()
    return True


def reconcile_one_list(cc_api, access_token, attio_list_id, cc_list_id, dry_run, force=False):
    attio_emails = attio_list_emails(attio_list_id)
    cc_contacts = cc_list_contacts(cc_api, access_token, cc_list_id)

    # Zero Attio members with a non-empty CC list is far more likely a
    # misconfiguration (wrong list_id, a companies/deals list with no
    # email_addresses attribute, a transient API hiccup) than "everyone
    # actually left" -- refuse to wipe the whole CC list in live mode unless
    # explicitly forced. Dry-run still shows the would-remove-everyone
    # result, which is exactly what should surface the mistake.
    if not force and not dry_run and not attio_emails and cc_contacts:
        return {
            "attio_list_id": attio_list_id, "cc_list_id": cc_list_id,
            "attio_member_count": 0, "cc_member_count": len(cc_contacts),
            "skipped": "Attio list has 0 members but CC list has "
                       f"{len(cc_contacts)} -- refusing to remove everyone. "
                       "Check attio_list_id is correct (right object type: "
                       "people, not companies/deals) or pass force=true.",
        }

    to_remove = {email: cid for email, cid in cc_contacts.items() if email not in attio_emails}

    removed, errors = [], []
    for email, contact_id in to_remove.items():
        if dry_run:
            removed.append(email)
            continue
        try:
            if remove_from_cc_list(cc_api, access_token, contact_id, cc_list_id):
                removed.append(email)
        except Exception as e:  # noqa: BLE001 — one bad contact shouldn't kill the batch
            errors.append({"email": email, "error": str(e)})

    return {
        "attio_list_id": attio_list_id,
        "cc_list_id": cc_list_id,
        "attio_member_count": len(attio_emails),
        "cc_member_count": len(cc_contacts),
        "would_remove" if dry_run else "removed": removed,
        "errors": errors,
    }
