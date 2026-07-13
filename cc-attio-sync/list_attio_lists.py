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

print("\nATTIO_LIST_MAP skeleton -- fill in the cc_key for each list you want")
print("reconciled (must match a key already in CC_LIST_MAP in deploy.sh):\n")
skeleton = {
    lst.get("api_slug", ""): {"list_id": lst.get("id", {}).get("list_id", ""), "cc_key": "TODO"}
    for lst in lists
}
print("  " + json.dumps(skeleton, indent=2))
