#!/usr/bin/env python3
"""
Dump your Constant Contact lists + UUIDs, ready to paste into CC_LIST_MAP.

Usage:
    export CC_CLIENT_ID=...
    export CC_CLIENT_SECRET=...
    export CC_REFRESH_TOKEN=...     # from get_refresh_token.py
    python list_cc_lists.py

Prints a skeleton mapping; rename the keys to whatever you'll send from Attio.
"""
import json
import os
import subprocess
import sys

import requests

TOKEN = "https://authz.constantcontact.com/oauth2/default/v1/token"
API = "https://api.cc.email/v3"

cid = os.environ.get("CC_CLIENT_ID")
secret = os.environ.get("CC_CLIENT_SECRET")
refresh = os.environ.get("CC_REFRESH_TOKEN")
if not (cid and secret and refresh):
    sys.exit("Set CC_CLIENT_ID, CC_CLIENT_SECRET, and CC_REFRESH_TOKEN first.")

# Note: this uses (and thus rotates) the refresh token. CC returns a NEW one
# below, which this script writes straight back to Secret Manager (see the
# gcloud call further down) — so it's safe to run any time, deployed or not.
r = requests.post(
    TOKEN,
    data={"grant_type": "refresh_token", "refresh_token": refresh},
    auth=(cid, secret), timeout=30,
)
r.raise_for_status()
tok = r.json()
access = tok["access_token"]
new_refresh = tok.get("refresh_token")

r = requests.get(
    f"{API}/contact_lists",
    headers={"Authorization": f"Bearer {access}"},
    params={"include_count": "true", "limit": 1000},
    timeout=30,
)
r.raise_for_status()
lists = r.json().get("lists", [])

print(f"\nFound {len(lists)} list(s):\n")
mapping = {}
for lst in lists:
    name = lst.get("name", "")
    lid = lst.get("list_id", "")
    count = lst.get("membership_count", "?")
    print(f"  {name:<40} {lid}   ({count} contacts)")
    key = name.lower().replace(" ", "-")
    mapping[key] = lid

print("\nCC_LIST_MAP skeleton (rename keys to what Attio will send):\n")
print("  " + json.dumps(mapping))

if new_refresh and new_refresh != refresh:
    print("\nThis call rotated your refresh token — persisting the new one to "
          "Secret Manager (CC_REFRESH_TOKEN)...")
    try:
        subprocess.run(
            ["gcloud", "secrets", "versions", "add", "CC_REFRESH_TOKEN", "--data-file=-"],
            input=new_refresh.encode("utf-8"), check=True,
        )
        print("Done — CC_REFRESH_TOKEN in Secret Manager is up to date.")
    except Exception as e:  # noqa: BLE001 — fall back to a manual instruction
        print(f"Could not persist automatically ({e}). Store it by hand:\n")
        print(f"   echo -n '{new_refresh}' | gcloud secrets versions add "
              "CC_REFRESH_TOKEN --data-file=-")
