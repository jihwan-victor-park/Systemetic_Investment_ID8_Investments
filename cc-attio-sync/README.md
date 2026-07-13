# Attio → Constant Contact list sync

A single webhook endpoint. When a person enters an Attio list, they get added to
the matching Constant Contact list. No n8n, no Zapier — one ~130-line Cloud Run
service holding the CC OAuth2 credentials.

```
Attio automation                  this service (Cloud Run)        Constant Contact
"record enters List X"  ──POST──▶  /attio-webhook  ──────────▶  POST /contacts/sign_up_form
                                   (refreshes CC token,           (create-or-update by email,
                                    rotates refresh token)         adds list membership)
```

Runs in the same GCP project/region as the rest of this repo's Cloud Run
services: `id8-investments` (project `137750788450`), `us-east4`.

## Setup, in order

**1. Register a Constant Contact developer app** (if you don't have one) at
   [developer.constantcontact.com](https://developer.constantcontact.com/) →
   My Applications → New Application. Set redirect URI to `https://localhost`
   (or set `CC_REDIRECT_URI` below to match whatever you register). Note the
   API key (`CC_CLIENT_ID`) and generate a client secret (`CC_CLIENT_SECRET`).

**2. Get a refresh token** (one time, local machine):
   ```bash
   pip install -r requirements.txt
   export CC_CLIENT_ID=...
   export CC_CLIENT_SECRET=...
   python get_refresh_token.py
   ```
   Opens a URL to approve in your browser, then paste back the redirected
   `?code=...`. Prints a `refresh_token` — that's `CC_REFRESH_TOKEN`.

**3. Create the secrets + IAM binding:**
   ```bash
   export CC_CLIENT_ID=...
   export CC_CLIENT_SECRET=...
   export CC_REFRESH_TOKEN=...              # from step 2
   export WEBHOOK_SECRET=$(openssl rand -hex 32)
   ./setup_secrets.sh
   ```
   Keep the `WEBHOOK_SECRET` value — you'll paste it into the Attio
   automation header in step 6.

**4. Get your Constant Contact list UUIDs:**
   ```bash
   export CC_CLIENT_ID=... CC_CLIENT_SECRET=... CC_REFRESH_TOKEN=...  # same as above
   python list_cc_lists.py
   ```
   This call rotates the refresh token; the script writes the new one straight
   back to the `CC_REFRESH_TOKEN` secret via `gcloud`, so it's safe to run
   before or after `setup_secrets.sh` / deploying.

**5. Edit `CC_LIST_MAP` in [deploy.sh](deploy.sh)** with the real mapping
   from step 4 — keyed by whatever string the Attio automation will send as
   `list`, valued by the CC list UUID.

**6. Deploy:**
   ```bash
   ./deploy.sh        # prints the webhook URL
   ```

**7. Build the Attio automation(s)** (one per list, or one keyed by list):
   - Trigger: **Record enters list** → your target list.
   - Action: **Send webhook** (HTTP request) → `https://<service-url>/attio-webhook`
   - Header: `X-Webhook-Secret: <the WEBHOOK_SECRET from step 3>`
   - JSON body, templated from the record:
     ```json
     { "email": "{{ record.email_addresses.0 }}",
       "list": "newsletter",
       "first_name": "{{ record.name.first_name }}",
       "last_name":  "{{ record.name.last_name }}" }
     ```
     (`list` must match a key in `CC_LIST_MAP`.)

**8. (Optional) Build the delete automation**, one, not per-list:
   - Trigger: **Record deleted**.
   - Action: **Send webhook** → `https://<service-url>/attio-delete-webhook`
   - Header: same `X-Webhook-Secret`.
   - JSON body: `{ "email": "{{ record.email_addresses.0 }}" }`
   - **This permanently deletes the Constant Contact contact** (CC's
     GDPR-style delete — removes them from every CC list, not just the ones
     this integration manages, and it's irreversible). If you only want them
     off *this* automation's list rather than gone from CC entirely, don't
     wire this up — ask for a "remove from list" variant instead.

## Test

```bash
curl -s -X POST "$URL/attio-webhook" \
  -H "X-Webhook-Secret: $SECRET" -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","list":"newsletter"}'
# -> {"ok": true, ...}  and the contact appears in that CC list

curl -s -X POST "$URL/attio-delete-webhook" \
  -H "X-Webhook-Secret: $SECRET" -H "Content-Type: application/json" \
  -d '{"email":"you@example.com"}'
# -> {"ok": true, "deleted": true, ...}  and the contact is gone from CC entirely

curl -s "$URL/health"
# -> {"ok": true, "lists": ["newsletter", ...]}
```

## Reconciling removals (Attio has no "removed from list" trigger)

Attio's automations can fire on **record added to list**, **list entry
updated**, or a manual **list entry command** — there is no trigger for
"record removed from a list" (confirmed directly against Attio's own
docs/support), so a removal can't be webhook-driven the way an add is.
`/reconcile` closes that gap by pulling instead of waiting to be pushed to:
called on a schedule, it re-reads each configured Attio List's current
membership and removes anyone from the matching Constant Contact list who's
no longer in it. It never deletes the CC contact or touches their other list
memberships — only the one list membership that fell out of sync.

**Setup:**
1. `export ATTIO_API_KEY=...` (same key `deal_intelligence`/`pipeline` already
   use) then `python list_attio_lists.py` to get each Attio List's `list_id`.
   The key needs `list_entry:read` and `list_configuration:read` scopes —
   add them on the key in Attio's workspace settings if this 403s (nothing
   List-related has used this key before now).
2. Fill in `ATTIO_LIST_MAP` in `deploy.sh` — `{"<attio_list_id>": "<key already in CC_LIST_MAP>", ...}`.
3. Deploy, then wire up a Cloud Scheduler job to call it (daily is reasonable
   for list hygiene — this isn't time-sensitive like the add webhook):
   ```bash
   gcloud scheduler jobs create http cc-attio-reconcile \
     --schedule="0 13 * * *" --uri="<service-url>/reconcile" \
     --http-method=POST --headers="X-Webhook-Secret=<WEBHOOK_SECRET>,Content-Type=application/json" \
     --message-body='{"dry_run": false}' \
     --oidc-service-account-email="<runtime-service-account>" --location=us-east4
   ```
   Point it straight at the Cloud Run URL, not the API Gateway one — Cloud
   Scheduler authenticates with its own OIDC token, so it needs
   `roles/run.invoker` on `cc-attio-sync` directly (grant that to whatever
   service account runs the job), and there's no need to route this
   particular call through the Gateway.

**Run it manually first, in dry-run** (the default — pass nothing, or
`{"dry_run": true}`):
```bash
curl -s -X POST "$URL/reconcile" -H "X-Webhook-Secret: $SECRET" \
  -H "Content-Type: application/json" -d '{}'
# -> {"ok": true, "dry_run": true, "results": [{"would_remove": [...], ...}]}
```
Read `would_remove` carefully before ever passing `{"dry_run": false}`. The
Constant Contact removal logic (`reconcile.py`) is built from best available
knowledge of CC's v3 API rather than freshly re-verified docs — it always
GETs the contact fresh and only mutates `list_memberships` on that exact
object (never reconstructs a request body from scratch, so a wrong
assumption fails loudly rather than corrupting other fields), but test it
dry-run, then live on one low-stakes list with a disposable test contact,
before trusting it against a real list.

## Audit log

Every sync/delete/removal attempt that reaches the Constant Contact API call
— success or CC rejecting it — is written to Firestore, collection
`cc_sync_log` (same GCP project/database `deal_intelligence`/hub-next already
use, see `deal_intelligence/firestore_push.py`): `action` (`"add"`,
`"delete"`, or `"remove_from_list"`), `email`, `list_key`, `cc_list_id`, `ok`,
`detail` (error text if `ok` is false, or `"dry_run"` for a dry-run
would-remove), `timestamp` (server-side, so it's not subject to app clock
skew). Query it from the Firestore console, or `gcloud firestore` / any
Firestore client, filtered on `email`, `list_key`, or `action`.

The Cloud Run service account needs `roles/datastore.user` for this to work
(same role `deal_intelligence`'s pipeline already needs for the same reason —
see its `config.py`). A logging failure never fails the webhook response;
the actual CC operation has already happened by the time this write is
attempted.

## Notes

- **`--max-instances 1` is deliberate.** CC rotates the refresh token on every
  refresh; a single instance keeps one owner of it. Volume (occasional list adds)
  is far below what one instance handles.
- This is **Attio → CC, one direction.** The initial CC → Attio load is a manual
  CSV export/import (one List per campaign). Doing both directions live would
  need loop-prevention; not built here.
- `setup_secrets.sh` is idempotent — re-run it any time to rotate `WEBHOOK_SECRET`
  or fix a bad `CC_REFRESH_TOKEN`; it adds a new secret version rather than
  failing on an existing secret.
