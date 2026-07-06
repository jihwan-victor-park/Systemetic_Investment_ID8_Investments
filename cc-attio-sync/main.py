"""
Attio → Constant Contact list-sync webhook.

One endpoint. Attio's native automation ("when a person enters List X") POSTs
here; this adds that person to the matching Constant Contact list. No n8n.

Why a server at all (and not a direct Attio→CC HTTP action): Constant Contact's
v3 API uses OAuth2. Access tokens expire in 24h and the refresh token ROTATES on
every use (the old one is invalidated). Attio's HTTP action can't manage that, so
this service holds the credentials, refreshes on demand, and persists the new
refresh token back to Secret Manager.

Deploy with --max-instances 1 (see deploy.sh): the rotating refresh token must
have a single owner, otherwise two instances race and invalidate each other.

Expected webhook body (you template this in the Attio automation):
    { "email": "jane@acme.com", "list": "<key in CC_LIST_MAP>",
      "first_name": "Jane", "last_name": "Doe" }   # names optional

Env / secrets:
    WEBHOOK_SECRET     shared secret; Attio sends it as X-Webhook-Secret
    CC_CLIENT_ID       Constant Contact app key
    CC_CLIENT_SECRET   Constant Contact app secret
    CC_REFRESH_TOKEN   current refresh token (rotated + rewritten by this service)
    CC_LIST_MAP        JSON: { "<attio list key>": "<cc list uuid>", ... }
"""
import json
import os
import threading
import time

import requests
from flask import Flask, request

app = Flask(__name__)

_GCP_PROJECT = "projects/137750788450"
CC_TOKEN_URL = "https://authz.constantcontact.com/oauth2/default/v1/token"
CC_API = "https://api.cc.email/v3"

# In-process token cache. With --max-instances 1 this is the single source of
# truth for the rotating refresh token; the lock serializes refreshes.
_lock = threading.Lock()
_access_token = None
_access_expiry = 0.0
_refresh_token = os.getenv("CC_REFRESH_TOKEN", "")


def _secret_name(key):
    return f"{_GCP_PROJECT}/secrets/{key}"


def _persist_refresh_token(new_token):
    """Write the rotated refresh token back as a new Secret Manager version."""
    global _refresh_token
    _refresh_token = new_token
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        client.add_secret_version(
            parent=_secret_name("CC_REFRESH_TOKEN"),
            payload={"data": new_token.encode("utf-8")},
        )
    except Exception as e:  # noqa: BLE001 — log and keep serving from memory
        app.logger.error("could not persist CC_REFRESH_TOKEN to Secret Manager: %s", e)


def _access():
    """Return a valid CC access token, refreshing (and rotating) if needed."""
    global _access_token, _access_expiry
    with _lock:
        if _access_token and time.time() < _access_expiry - 120:
            return _access_token
        if not _refresh_token:
            raise RuntimeError("CC_REFRESH_TOKEN is empty — re-do the OAuth2 grant")
        resp = requests.post(
            CC_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": _refresh_token},
            auth=(os.environ["CC_CLIENT_ID"], os.environ["CC_CLIENT_SECRET"]),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        tok = resp.json()
        _access_token = tok["access_token"]
        _access_expiry = time.time() + int(tok.get("expires_in", 86400))
        if tok.get("refresh_token") and tok["refresh_token"] != _refresh_token:
            _persist_refresh_token(tok["refresh_token"])
        return _access_token


def _list_map():
    return json.loads(os.environ.get("CC_LIST_MAP", "{}"))


@app.get("/health")
def health():
    return {"ok": True, "lists": list(_list_map().keys())}


@app.post("/attio-webhook")
def attio_webhook():
    if os.environ.get("WEBHOOK_SECRET") and \
       request.headers.get("X-Webhook-Secret") != os.environ["WEBHOOK_SECRET"]:
        return {"error": "unauthorized"}, 401

    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    list_key = (body.get("list") or "").strip()
    if not email or not list_key:
        return {"error": "missing email or list"}, 400

    cc_list_id = _list_map().get(list_key)
    if not cc_list_id:
        return {"error": f"no CC list mapped for '{list_key}'"}, 422

    # sign_up_form is CC v3's create-or-update-by-email endpoint; it adds the
    # list membership whether or not the contact already exists.
    payload = {"email_address": email, "list_memberships": [cc_list_id]}
    if body.get("first_name"):
        payload["first_name"] = body["first_name"]
    if body.get("last_name"):
        payload["last_name"] = body["last_name"]

    r = requests.post(
        f"{CC_API}/contacts/sign_up_form",
        json=payload,
        headers={"Authorization": f"Bearer {_access()}",
                 "Content-Type": "application/json"},
        timeout=30,
    )
    if r.status_code >= 300:
        app.logger.error("CC error %s: %s", r.status_code, r.text)
        return {"error": "constant contact rejected the request",
                "status": r.status_code, "detail": r.text}, 502
    return {"ok": True, "email": email, "cc_list_id": cc_list_id}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
