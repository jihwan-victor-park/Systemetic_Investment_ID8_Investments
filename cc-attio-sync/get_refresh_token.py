#!/usr/bin/env python3
"""
One-time: get a Constant Contact refresh token (authorization-code grant).

The refresh token is what cc-attio-sync stores and rotates. You only run this
once; after that the service keeps itself alive off the rotating token.

Usage:
    export CC_CLIENT_ID=87e4ded1-...        # API Key from the CC app
    export CC_CLIENT_SECRET=...             # from "Generate Client Secret"
    python get_refresh_token.py

Then: open the printed URL, approve, copy the ?code=... from the localhost
redirect (the page won't load — that's fine), and paste it back here.

Redirect URI defaults to https://localhost — it MUST match what's registered on
the CC app. Override with CC_REDIRECT_URI if you registered something else.
"""
import os
import sys
import urllib.parse

import requests

AUTHZ = "https://authz.constantcontact.com/oauth2/default/v1/authorize"
TOKEN = "https://authz.constantcontact.com/oauth2/default/v1/token"

client_id = os.environ.get("CC_CLIENT_ID")
client_secret = os.environ.get("CC_CLIENT_SECRET")
redirect_uri = os.environ.get("CC_REDIRECT_URI", "https://localhost")
if not client_id or not client_secret:
    sys.exit("Set CC_CLIENT_ID and CC_CLIENT_SECRET in the environment first.")

params = urllib.parse.urlencode({
    "client_id": client_id,
    "redirect_uri": redirect_uri,
    "response_type": "code",
    "scope": "contact_data offline_access",
    "state": "id8",
})
print("\n1) Open this URL, log in, and approve:\n")
print(f"   {AUTHZ}?{params}\n")
print("2) Your browser redirects to "
      f"{redirect_uri}/?code=XXXX  (the page won't load — that's expected).\n")

pasted = input("3) Paste the full redirected URL (or just the code): ").strip()
if "code=" in pasted:
    code = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query).get("code", [pasted])[0]
else:
    code = pasted

resp = requests.post(
    TOKEN,
    data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
    auth=(client_id, client_secret),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    timeout=30,
)
if resp.status_code >= 300:
    sys.exit(f"\nToken exchange failed ({resp.status_code}): {resp.text}")

tok = resp.json()
print("\n✅ Success.\n")
print("refresh_token (store as the CC_REFRESH_TOKEN secret):\n")
print(f"   {tok['refresh_token']}\n")
print(f"(access_token is valid ~{tok.get('expires_in', 86400)}s; the service "
      "fetches its own, you don't need to keep it.)")
