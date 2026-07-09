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

**7. Build the Attio automation** (one per list, or one keyed by list):
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

## Test

```bash
curl -s -X POST "$URL/attio-webhook" \
  -H "X-Webhook-Secret: $SECRET" -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","list":"newsletter"}'
# -> {"ok": true, ...}  and the contact appears in that CC list

curl -s "$URL/health"
# -> {"ok": true, "lists": ["newsletter", ...]}
```

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
