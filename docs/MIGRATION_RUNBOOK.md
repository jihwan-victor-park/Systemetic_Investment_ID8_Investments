# ID8 Intelligence — Full Migration Runbook

One ordered place to take everything from "works on my laptop" to "runs in the
cloud." Ties together the detailed docs already in this repo:

- `n8n-cloudrun/MIGRATION_PLAN.md` + `deploy.sh` + `ENV_REFERENCE.md` — n8n → Cloud Run
- `n8n-cloudrun/ACCOUNT_REQUESTS.md` — GCP project + IAM the account owner must grant
- `n8n-cloudrun/WEBHOOK_SETUP.md` — Apps Script triggers
- `hub/cloudbuild.yaml` + `hub/Dockerfile` — the Docusaurus hub → Cloud Run
- `docs/CLOUD_INTELLIGENCE_PLAN.md` — the overall architecture

**Project:** `id8-investments`  ·  **Region:** `us-east4`  ·  Flask app already
live at `id8-137750788450.us-east4.run.app`.

---

## Two paths — pick based on what you actually need now

### Path A — "Screening ratings in the deal email" (small, ~1 hour)
This does NOT require migrating n8n to the cloud or deploying the hub. It needs:
1. Redeploy the Flask app with the new `/screen-deals` endpoint (Phase 1).
2. Set `PERPLEXITY_API_KEY` + `ATTIO_API_KEY` on that service (Phase 1).
3. Add a screening node + email step in n8n — works against your **local** n8n
   too, since it just HTTP-calls the cloud Flask app (Phase 3).

That's the whole thing. The Attio fit-score fields are NOT needed (writes are
skipped when unset; the email is built regardless).

### Path B — "Migrate everything to the cloud" (the full job)
Everything in Path A, plus n8n itself on Cloud Run (Phase 2), the hub deployed
(Phase 4), full deal-intelligence write-back (Phase 5), and the Apps Script
triggers repointed (Phase 6). Do this when you want it all off the laptop and
running 24/7. Phases 2/4/5/6 are independent of each other.

---

## Phase 0 — Tooling & access (one time)

- [ ] **Install gcloud** (not currently on this machine):
      `brew install --cask google-cloud-sdk` then `gcloud auth login` and
      `gcloud config set project id8-investments`.
- [ ] **Docker Desktop** running (needed for the n8n image build in Phase 2).
- [ ] **GCP access** — if the Flask app is already deployed, the project and your
      IAM access already exist; skip. If starting fresh, the account owner does the
      `ACCOUNT_REQUESTS.md` checklist (create project, grant you Owner, OAuth consent).
- [ ] **Secrets in hand:** `ATTIO_API_KEY`, `PERPLEXITY_API_KEY`,
      `APOLLO_API_KEY` (master), `ANTHROPIC_API_KEY`.

---

## Phase 1 — Redeploy the Flask pipeline (with `/screen-deals`)

The new code is committed but not yet in the cloud. The build is ready: root
`Dockerfile` + `Procfile` both do `--chdir pipeline app:app`, and `python-docx`
is in `requirements.txt`.

- [ ] **Point the deploy at the NEW repo.** The service was building from
      `pb-attio-pipeline`. You pushed to `id8-intelligence`. Either repoint the
      Cloud Build trigger to `id8-intelligence` / `main`, or do a one-off source deploy.
- [ ] **Deploy** (from the repo root, once gcloud is installed):
      ```bash
      gcloud run deploy id8 \
        --source . \
        --region us-east4 \
        --update-env-vars PERPLEXITY_API_KEY=...,ATTIO_API_KEY=...
      ```
      (Prefer Secret Manager over plaintext env for the keys — `--update-secrets`.)
- [ ] **Verify:**
      ```bash
      curl -X POST https://id8-137750788450.us-east4.run.app/screen-deals \
        -H 'Content-Type: application/json' -d '{"dry_run": true}'
      # -> {"status":"started","poll":"/screen-deals/status"}
      curl https://id8-137750788450.us-east4.run.app/screen-deals/status
      # poll until {"status":"complete", ...}; the result includes email_html
      ```
- **Done when:** `/screen-deals/status` returns `status: complete` with an
  `email_html` field and a `stage1` array.

> `dry_run: true` skips Attio write-back but still reads Qualified deals and runs
> Perplexity, so it's the safe first smoke test. Remove it for real runs.

---

## Phase 2 — Migrate n8n to Cloud Run

> **✅ Done (superseded, Jul 2026):** This already happened, and not quite this
> way — n8n runs on **Cloud SQL Postgres** (`n8n-db`, `db-f1-micro`), not Neon;
> there was never a `NEON_DATABASE_URL` in practice. Triggers are native
> Google Drive/Sheets polling nodes, not the webhook import described below.
> `deploy.sh` no longer needs the `NEON_DATABASE_URL` env var at all. Kept here
> for historical context only.

Follow `n8n-cloudrun/MIGRATION_PLAN.md`. Condensed:

- [ ] Free Neon Postgres project → copy the connection string.
- [ ] (Optional) Grab `encryptionKey` from local `~/.n8n/config` to keep saved creds.
- [ ] Run the deploy:
      ```bash
      cd n8n-cloudrun
      export NEON_DATABASE_URL="postgres://...:...@...neon.tech/...?sslmode=require"
      export N8N_ENCRYPTION_KEY="<from ~/.n8n/config, or omit to generate>"
      ./deploy.sh
      ```
- [ ] Re-authorize Google Drive + Gmail credentials against the new n8n URL
      (OAuth callbacks are tied to the hostname — see plan Phase 4).
- [ ] Import `ID8_PB-Attio_webhook.json`, reattach creds, confirm the HTTP nodes
      point at the Flask app.
- [ ] Test with one Drive drop, then **deactivate the LOCAL workflow** so files
      aren't processed twice.
- **Done when:** a Drive drop processed by the cloud n8n lands in Attio and emails.

---

## Phase 3 — Add the screening node + rating email in n8n

No plugins to install — all built-in nodes. After the intake email's deals are
in Attio, add this branch (works on local or cloud n8n):

1. **HTTP Request** node — start the screen:
   - Method `POST`, URL `https://id8-137750788450.us-east4.run.app/screen-deals`
   - Body (JSON): `{ "stage1_only": true }`
2. **Loop until done** — poll the status:
   - **Wait** node: 30 seconds.
   - **HTTP Request** node: `GET .../screen-deals/status`
   - **IF** node: `{{ $json.status }}` equals `complete` → exit loop; else → back to Wait.
   - (Perplexity scoring runs a few seconds per deal, so a small qualified pool
     finishes inside a minute or two.)
3. **Gmail / Send Email** node:
   - **Set the email type to HTML** (not plain text).
   - Body: `{{ $json.email_html }}`  (the field returned by the status endpoint)
   - Subject e.g. `Deal Intelligence — Stage 1 Screen`.

- **Done when:** the email arrives with the rating table + per-category scores +
  rationale, gated deals flagged. That is the goal.

> **Backlog caveat:** `/screen-deals` currently scores **every** Qualified deal in
> Attio, so triggering it per drop re-emails the whole backlog. The fix is the
> "skip already-scored" guard (only score deals without a `fit_score`); ask Claude
> to add it once the Attio `fit_score` field exists. Until then, run it on a daily
> schedule as a digest rather than per-drop.

---

## Phase 4 — Deploy the hub (Docusaurus) — independent

Not needed for the email. Deploy when you want the browsable Research/Companies
pages and the Capabilities view online. `hub/cloudbuild.yaml` + `hub/Dockerfile`
are ready (note: hub cloudbuild defaults to `us-central1` / repo `id8-hub` — align
the region with the rest if you prefer).

- [ ] Create the Artifact Registry repo + Cloud Build trigger on `id8-intelligence`,
      path filter `hub/**`.
- [ ] Deploy private (`--no-allow-unauthenticated`), put IAP in front scoped to
      `@id8investments.com` (per `CLOUD_INTELLIGENCE_PLAN.md` §2), map the domain.
- [ ] Add a weekly Cloud Scheduler → Cloud Build rebuild so generated pages refresh.
- **Done when:** `intel.id8investments.com` loads behind Google login.

> Company pages are generated where they can be committed to git (local/CI), then
> the hub rebuilds from the repo — NOT written by the Cloud Run Flask container
> (its disk is ephemeral). So the deal-screen pages flow: run the pipeline with
> `--no-publish` off locally/CI → commit the generated `hub/docs/research/companies/*`
> → hub rebuild publishes them.

---

## Phase 5 — Full deal-intelligence activation (later)

- [ ] Create the Attio Deals fields and set their slugs via the `DI_SLUG_*` env
      vars (`deal_intelligence/config.py`): `fit_score` (number), `fit_gate`
      (select Yes/No), `fit_rationale` (text). Confirm `domain`/`round`/`hq` read slugs.
- [ ] Add the "skip already-scored" guard (Phase 3 caveat).
- [ ] Wire Stage 2 (deep research + memo) — `stage1_only: false` + `ANTHROPIC_API_KEY`,
      plus the `memo_url`/`final_score` write-back fields.
- [ ] (Optional) Calibration loop — accumulate hand-corrected scores as few-shot
      anchors so scoring drifts toward ID8's taste. Stays Perplexity-only.

---

## Phase 6 — Apps Script triggers

Per `n8n-cloudrun/WEBHOOK_SETUP.md` — repoint the Drive-watch / Sheet onChange /
daily cron triggers at the new n8n webhook URLs once Phase 2 is live.

---

## Phase 7 — Attio → Constant Contact list sync (independent)

Not related to the pipeline/n8n/hub above — a separate small Cloud Run service.
Full steps in `cc-attio-sync/README.md`; condensed:

- [x] Register a Constant Contact developer app → `CC_CLIENT_ID`/`CC_CLIENT_SECRET`.
- [x] `python get_refresh_token.py` (one-time OAuth grant) → `CC_REFRESH_TOKEN`.
- [x] `./setup_secrets.sh` → creates the 4 secrets + grants the runtime service
      account read access and `secretVersionAdder` on `CC_REFRESH_TOKEN`.
- [x] `python list_cc_lists.py` → real CC list UUIDs; paste into `CC_LIST_MAP`
      in `deploy.sh`.
- [x] `./deploy.sh` → deployed, but the Cloud Run service is **not** directly
      public — see the IAM note below.
- [x] Build the Attio automation(s): **Record enters list → Send webhook** →
      the API Gateway URL below, header `X-Webhook-Secret`.
- **Done when:** adding someone to an Attio list makes them appear in the
  matching Constant Contact list within a few seconds. Confirmed working
  2026-07-13.

> **⚠️ Cloud Run's `--allow-unauthenticated` does not work in this org.** A
> Domain Restricted Sharing org policy (`iam.allowedPolicyMemberDomains`,
> allowed value `C03y3a2wj` only) blocks granting `allUsers` on *any*
> resource — `deploy.sh`'s `--allow-unauthenticated` silently fails to bind,
> and `cc-attio-sync` stayed IAM-private (401/403 for every caller) despite
> looking deployed. Nobody currently holds `roles/orgpolicy.policyAdmin` or
> even org-level IAM read access on this org (id `238943261662`), so
> loosening the policy isn't a quick fix.
>
> **Fix used:** front the private Cloud Run service with **API Gateway**,
> which exposes a public endpoint through its own (non-IAM) access model and
> calls the backend using a dedicated service account
> (`cc-attio-gateway-invoker@...iam.gserviceaccount.com`, granted
> `roles/run.invoker` — an in-project principal, so the org policy doesn't
> block it). `cc-attio-sync` itself never gets `allUsers`.
>
> Public webhook URL is now the **Gateway** hostname, not the raw
> `*.run.app` URL: `https://cc-attio-sync-gw-1ra59gma.uk.gateway.dev/attio-webhook`.
> Setup: `gcloud beta services identity create --service=apigateway.googleapis.com`
> → `iam.serviceAccountTokenCreator` binding for that agent on the dedicated SA
> → `api-gateway apis create` → `api-configs create --backend-auth-service-account=...`
> → `gateways create`. **Any future service that needs to be public-facing in
> this GCP project will hit the same wall and needs the same pattern** (or
> someone getting org-policy-admin rights first).

---

## Critical path for the email goal (Path A)

```
Phase 0 (gcloud + keys)  ->  Phase 1 (deploy Flask + /screen-deals)  ->  Phase 3 (n8n nodes)
```

Everything else (n8n cloud migration, hub, Attio fields, Stage 2) can come after.
