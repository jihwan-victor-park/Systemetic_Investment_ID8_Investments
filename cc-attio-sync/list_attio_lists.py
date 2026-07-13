#!/usr/bin/env python3
"""
Dump your Attio Lists + IDs, ready to paste into ATTIO_LIST_MAP (reconcile.py).

Usage:
    export ATTIO_API_KEY=...    # same key deal_intelligence/pipeline already use
    python list_attio_lists.py

The API key needs the `list_configuration:read` scope (and `list_entry:read`
for reconcile.py itself) -- check/add these on the key in Attio's workspace
settings (Settings -> API -> the key -> Scopes) if this comes back empty or
403s despite the key working fine for Records elsewhere in this repo.
"""
import json
import os
import sys

import requests

ATTIO_BASE = "https://api.attio.com/v2"

api_key = os.environ.get("ATTIO_API_KEY")
if not api_key:
    sys.exit("Set ATTIO_API_KEY first (same key used by deal_intelligence/pipeline).")

r = requests.get(
    f"{ATTIO_BASE}/lists",
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=30,
)
r.raise_for_status()
lists = r.json().get("data", [])

print(f"\nFound {len(lists)} list(s):\n")
for lst in lists:
    name = lst.get("name", "")
    slug = lst.get("api_slug", "")
    list_id = lst.get("id", {}).get("list_id", "")
    parent = ", ".join(lst.get("parent_object", []))
    print(f"  {name:<40} slug={slug:<30} list_id={list_id}   (on {parent})")

people_lists = [lst for lst in lists if "people" in (lst.get("parent_object") or [])]
skipped = len(lists) - len(people_lists)
if skipped:
    print(f"\n({skipped} list(s) above are on companies/deals, not people -- no "
          "email_addresses attribute, so they're excluded below. Reconciling "
          "one of those would see 0 Attio members and try to remove everyone "
          "from the matching CC list; reconcile.py refuses that by default.)")

print("\nATTIO_LIST_MAP skeleton -- this is the ACTUAL shape main.py reads:")
print("{ <attio list_id>: \"<cc_key already in CC_LIST_MAP>\" }.")
print("Replace each null below with the matching CC_LIST_MAP key, delete any")
print("list you don't want reconciled, then paste the result into deploy.sh:\n")
skeleton = {lst.get("id", {}).get("list_id", ""): None for lst in people_lists}
print("  " + json.dumps(skeleton, indent=2))
