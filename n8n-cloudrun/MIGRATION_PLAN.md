# Migrating n8n from local → Google Cloud Run

**Goal:** move your locally-running n8n (the `ID8 PB-Attio` workflow) onto Google
Cloud Run, backed by a managed Postgres database, running 24/7 so the Google
Drive polling triggers keep firing.

**Target architecture**

```
  Google Drive (folder watch)
        │  every-minute poll
        ▼
  ┌─────────────────────────┐        ┌──────────────────────┐
  │  n8n  (Cloud Run)        │  SQL   │  Cloud SQL Postgres  │
  │  min=1, max=1, CPU on    │◄──────►│  (workflows, creds,  │
  │  region: us-east4        │ socket │   execution history) │
  └───────────┬─────────────┘        └──────────────────────┘
              │ HTTP POST
              ▼
  Your Flask app (already on Cloud Run: id8-…us-east4.run.app)
              │
              ▼
  Gmail send  →  oscar@ / isabella@id8investments.com
```

Put n8n in the **same project and region (`us-east4`)** as your existing Flask
service so the internal HTTP hops stay fast and within one project.

---

## Why this shape (the one thing to understand)

Cloud Run is built for stateless, request-driven services that **scale to zero**.
n8n is the opposite: it's a long-lived app that must stay awake to poll Google
Drive every minute and to keep its data. Two consequences drive every decision below:

1. **It must never scale to zero** → `--min-instances=1` with CPU always
   allocated (`--no-cpu-throttling`). Otherwise the every-minute Drive triggers
   silently stop when the container is idle.
2. **Its disk is ephemeral** → SQLite (n8n's default) and the auto-generated
   encryption key live on a filesystem that's wiped on every restart/redeploy.
   So we move state to **Cloud SQL Postgres** and pin the **encryption key** in
   Secret Manager.
3. **Exactly one instance** → `--max-instances=1`. A second instance would poll
   Drive a second time and double-process files. Running more than one needs
   n8n "queue mode" (Redis + workers), which your volume doesn't justify.

---

## Phase 0 — Capture what's on your local machine

Before touching the cloud, grab two things from your laptop's n8n.

1. **The encryption key.** Open `~/.n8n/config` and copy the `encryptionKey`
   value. Reusing it in the cloud lets your saved credentials migrate without
   re-encryption headaches. (If you'd rather just re-authenticate everything
   fresh in the cloud — which you'll partly have to do for OAuth anyway — you
   can skip this and let `deploy.sh` generate a new key.)

2. **Your workflows.** You already have `ID8 PB-Attio.json`. If you have others,
   export them from the local UI (or `n8n export:workflow --all --output=wf.json`).

> Credentials note: Google Drive and Gmail use **OAuth**. OAuth callbacks are
> tied to the n8n hostname, which is changing. So regardless of the encryption
> key, you'll re-authorize those two credentials against the new Cloud Run URL
> (Phase 4). The encryption key mainly matters for non-OAuth secrets.

---

## Phase 1 — One-time GCP setup

All automated by `deploy.sh`, but conceptually:

- Enable APIs: Cloud Run, Cloud SQL Admin, Artifact Registry, Secret Manager, Cloud Build.
- Create an **Artifact Registry** Docker repo (Cloud Run deploys images from your
  own registry).
- Create a **Cloud SQL Postgres 16** instance (`db-custom-1-3840`: 1 vCPU /
  3.75 GB — the smallest tier that runs n8n comfortably), plus a `n8n` database
  and `n8n` user.
- Store the **encryption key** and **DB password** in **Secret Manager** and
  grant the Cloud Run runtime service account read access.

---

## Phase 2 — Build the image

`Dockerfile` is a thin wrapper over the official `n8nio/n8n` image, pinned to a
specific version (don't use `:latest` in production). `deploy.sh` builds it with
Cloud Build and pushes to Artifact Registry.

---

## Phase 3 — Deploy to Cloud Run

`deploy.sh` deploys with the critical flags (`--min-instances=1`,
`--max-instances=1`, `--no-cpu-throttling`, `--add-cloudsql-instances`,
`--port=5678`) and wires env vars + secrets. See `ENV_REFERENCE.md` for what each
variable does.

It deploys **twice**: once to learn the assigned `*.run.app` URL, then again with
`WEBHOOK_URL` set to that URL (n8n needs to know its own public address for OAuth
callbacks and webhooks).

---

## Phase 4 — Re-connect Google OAuth

1. Open the new n8n URL, create your **owner account** (set a strong password —
   the service is public, so anyone with the URL hits the login page).
2. In **Google Cloud Console → APIs & Services → Credentials**, edit the OAuth
   2.0 Client used by your Drive/Gmail credentials and add this **Authorized
   redirect URI**:

   ```
   https://<your-n8n-url>.run.app/rest/oauth2-credential/callback
   ```

3. In n8n, open the **Google Drive** and **Gmail** credentials and click
   *Connect / Sign in with Google* to re-authorize against the new URL.

---

## Phase 5 — Import and validate the workflow

1. Import `ID8 PB-Attio.json` (Workflows → Import from File).
2. Reattach the re-authorized credentials to the Drive/Gmail nodes (n8n flags
   nodes whose credentials need re-selecting).
3. Confirm the **HTTP Request** nodes still point at your Flask service
   (`https://id8-137750788450.us-east4.run.app/process` and `/process-watchlist`).
4. **Test before going live:** drop a test file into the watched Drive folder and
   watch Executions. Verify the email sends and Attio updates.
5. Activate the workflow (toggle top-right).

---

## Phase 6 — Cutover

1. Once the cloud instance produces correct results, **deactivate the workflow on
   your local n8n** so the same Drive files aren't processed twice.
2. Keep the local instance around for a few days as a fallback, then retire it.

---

## Rollback

If something misbehaves, deactivate the cloud workflow and re-activate the local
one — both read the same Drive folders, so you lose no functionality. Your data
and encryption key remain in Cloud SQL / Secret Manager for the next attempt.

---

## Rough monthly cost (verify against current GCP pricing)

| Item | Config | Est. /mo (USD) |
|---|---|---|
| Cloud Run | 1 vCPU, 2 GB, min=1, CPU always on (~730 hrs) | ~$25–45 |
| Cloud SQL | `db-custom-1-3840`, zonal, ~10 GB SSD | ~$25–35 |
| Artifact Registry + Secret Manager | minimal | ~$1 |
| **Total** | | **~$50–80/mo** |

Cheaper levers if needed: drop Cloud SQL to a shared-core tier
(`db-f1-micro`-class) and Cloud Run to 1 GB RAM — fine for your low volume,
trims to roughly **$30–45/mo**. The always-on instance is the unavoidable cost
of keeping polling triggers alive; there's no scale-to-zero option that keeps
them working.

---

## Gotchas checklist

- [ ] **Encryption key is permanent.** Lose it and every stored credential
      becomes unreadable. It's in Secret Manager — don't delete that secret.
- [ ] **Don't run local + cloud active at once** (double-processing).
- [ ] **`--max-instances=1`.** Never raise it without switching to queue mode.
- [ ] **Auth the editor.** The service is `--allow-unauthenticated` so OAuth
      callbacks reach it; n8n's own login is your only gate. Use a strong owner
      password. (Optional hardening: put it behind IAP or n8n basic auth.)
- [ ] **Pin the n8n version** in the Dockerfile; upgrade deliberately, not via `:latest`.
- [ ] **Binary data** (your downloaded Drive files) is held transiently in the
      container during a run — fine on ephemeral disk since each execution is
      self-contained. No extra storage needed.
