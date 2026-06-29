# ID8 Intelligence Pipeline — Technical Specification

**Version:** 1.0  
**Date:** June 2026  
**Owner:** Oscar Varas  
**Infrastructure account:** ID8 GCP project (managed by firm / third-party account)

---

## 1. System Overview

A fully automated deal intelligence and data pipeline running on Google Cloud Run,
orchestrated by self-hosted n8n. Apps Script handles all Google Workspace triggers
(Drive, Sheets). All data lands in Attio (CRM) or is delivered via Gmail digest.

```
┌─────────────────────────────────────────────────────────────────┐
│  TRIGGERS (Google Apps Script — free, runs on Google's servers) │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ Drive folder    │  │ Sheet change │  │ Time-based         │ │
│  │ watch (5 min)   │  │ (Jesse's     │  │ (daily RSS/SEC     │ │
│  │ PB / Watch /    │  │  Deals sheet)│  │  scan, 7am ET)     │ │
│  │ Top10 folders   │  └──────┬───────┘  └─────────┬──────────┘ │
│  └──────┬──────────┘         │                    │            │
└─────────┼────────────────────┼────────────────────┼────────────┘
          │   HTTP POST (webhook)                   │
          ▼                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  n8n  (Google Cloud Run — boss's GCP project, us-east4)        │
│  min-instances=1, max-instances=1, 1 vCPU / 1Gi               │
│                                                                 │
│  Workflows:                                                     │
│  ① PitchBook weekly drop    → process Excel → Attio + email    │
│  ② Watchlist drop           → process Excel → Attio + email    │
│  ③ Top 10 VC drop           → process Excel → Attio + email    │
│  ④ Jesse's Deals            → read Sheet   → Attio + email     │
│  ⑤ Daily deal digest        → RSS scan     → filter → email    │
│  ⑥ Portfolio monitoring     → news scan    → Attio notes       │
│  ⑦ LP intelligence (SEC)    → 13F scan     → Attio + email     │
│  ⑧ Competitive VC radar     → news scan    → filter → email    │
└──────────────────┬──────────────────────────────────────────────┘
                   │ HTTP POST
          ┌────────┴────────┐
          ▼                 ▼
┌──────────────────┐  ┌─────────────────────────────────┐
│  app.py          │  │  External APIs (all free)       │
│  (Cloud Run,     │  │  - SEC EDGAR                    │
│   same project)  │  │  - RSS feeds                    │
│                  │  │  - GDELT                        │
│  Attio write     │  │  - Google Alerts → RSS          │
│  layer: deals,   │  └─────────────────────────────────┘
│  companies,      │
│  investors,      │
│  LP screening    │
└──────────┬───────┘
           │ REST API
           ▼
    ┌─────────────┐       ┌──────────────┐
    │   Attio CRM │       │  Gmail       │
    │  (deals,    │       │  (digests,   │
    │   companies,│       │   alerts)    │
    │   LPs)      │       └──────────────┘
    └─────────────┘
```

---

## 2. Infrastructure Components

### 2.1 Google Cloud Run — n8n

| Parameter | Value |
|---|---|
| Image | `docker.n8n.io/n8nio/n8n:1.108.2` (pinned) |
| Region | `us-east4` |
| CPU | 1 vCPU |
| Memory | 1 Gi |
| Min instances | 1 (always warm — webhooks land instantly) |
| Max instances | 1 (n8n regular mode; single-instance required) |
| CPU throttling | Yes (default) — CPU idles cheap between executions |
| Timeout | 3600s |
| Port | 5678 |
| Estimated cost | ~$8-10/mo |

### 2.2 Google Cloud Run — app.py (Flask pipeline)

| Parameter | Value |
|---|---|
| Runtime | Python 3.12 |
| CPU | 1 vCPU |
| Memory | 512 Mi |
| Min instances | 0 (scale to zero — only called by n8n) |
| Max instances | 3 |
| Timeout | 300s |
| Estimated cost | ~$0-1/mo |

### 2.3 Neon Postgres (n8n database)

| Parameter | Value |
|---|---|
| Provider | neon.tech |
| Plan | Free tier |
| Storage | 0.5 GB (n8n uses ~50-100 MB) |
| Connection | TLS connection string in Secret Manager |
| Estimated cost | $0/mo |

### 2.4 Artifact Registry

Stores Docker images for both Cloud Run services.

| Parameter | Value |
|---|---|
| Repo name | `n8n` (for n8n image), `id8-pipeline` (for app.py) |
| Region | `us-east4` |
| Format | Docker |
| Estimated cost | ~$0.10/mo (storage for 2 small images) |

### 2.5 Secret Manager

| Secret name | Contents |
|---|---|
| `n8n-encryption-key` | n8n credential encryption key (generate once, never change) |
| `n8n-database-url` | Neon Postgres connection string |
| `attio-api-key` | Attio API key |

### 2.6 Google Apps Script

Standalone project deployed under a Google account with access to the Drive
folders and Jesse's Deals spreadsheet.

| Trigger | Handler | Fires |
|---|---|---|
| Time-based (every 5 min) | `checkFolders()` | Checks 3 Drive folders for new files |
| Spreadsheet onChange | `jesseTrigger()` | Fires when Jesse's Deals sheet is edited |
| Time-based (daily 6:50am ET) | `runDailyScans()` | Kicks off RSS/SEC intelligence workflows (future) |

---

## 3. n8n Workflows — Full List

### Existing (migrated from local n8n)

| # | Workflow | Trigger | Endpoint | Output |
|---|---|---|---|---|
| ① | PitchBook Weekly Drop | Webhook `pitchbook-drop` | `POST /process` | Attio deals + email |
| ② | Watchlist Drop | Webhook `watchlist-drop` | `POST /process-watchlist` | Attio deals + email |
| ③ | Top 10 VC Drop | Webhook `top10-drop` | `POST /process-top10` | Attio deals + email |
| ④ | Jesse's Deals | Webhook `jesse-deals` | `POST /process-jesse` | Attio deals + email |

### Future (intelligence layer — not in scope for initial deploy)

| # | Workflow | Trigger | Logic | Output |
|---|---|---|---|---|
| ⑤ | Daily Deal Digest | Daily 7am (Apps Script) | Fetch 15 RSS feeds → filter by sector/stage | Email digest |
| ⑥ | Portfolio Monitoring | Daily 7am | Google Alerts RSS per portfolio company | Attio note on company record |
| ⑦ | LP Intelligence | Weekly Mon 7am | SEC EDGAR 13F filings → filter target LPs | Attio LP note + email |
| ⑧ | Competitive VC Radar | Weekly Mon 7am | RSS (StrictlyVC, The Information, PEHub) → filter by sector | Email digest |

AI summarization (Perplexity or similar) can be layered into any of these later without structural changes.

---

## 4. New app.py Endpoints (to be built)

| Endpoint | Purpose | Called by |
|---|---|---|
| `POST /intel/portfolio-news` | Receives news items, writes note to Attio company record | n8n workflow ⑥ |
| `POST /intel/lp-activity` | Receives SEC filing data, writes note to Attio LP record | n8n workflow ⑦ |

Existing endpoints (`/process`, `/process-watchlist`, `/process-top10`, `/process-jesse`) unchanged.

---

## 5. Deployment Steps

### Phase 1 — GCP Setup (boss / account owner)

1. Create GCP project `id8-pipeline` (or reuse existing)
2. Link billing account
3. Enable APIs: Cloud Run, Artifact Registry, Secret Manager, Cloud Build
4. Grant Oscar IAM roles (see Section 7)
5. Configure OAuth consent screen (internal, G Suite domain)
6. Add OAuth redirect URI: `https://n8n-[hash].us-east4.run.app/rest/oauth2-credential/callback`
   *(URL known after first deploy — can be updated)*

### Phase 2 — Neon (Oscar)

1. Create free account at neon.tech
2. Create project `id8-n8n`
3. Copy connection string → stored in Secret Manager by deploy.sh

### Phase 3 — n8n Deploy (Oscar)

```bash
cd n8n-cloudrun/
export NEON_DATABASE_URL="postgres://..."
export N8N_ENCRYPTION_KEY="<key from local ~/.n8n/config>"
./deploy.sh
```

### Phase 4 — app.py Deploy (Oscar)

```bash
cd ..  # repo root
gcloud run deploy id8-pipeline \
  --source . \
  --region us-east4 \
  --min-instances 0 \
  --max-instances 3 \
  --memory 512Mi \
  --set-secrets "ATTIO_API_KEY=attio-api-key:latest"
```

### Phase 5 — n8n Configuration (Oscar, in browser)

1. Open n8n URL, create owner account
2. Add Google Drive OAuth credential (re-auth)
3. Add Gmail OAuth credential (re-auth)
4. Add Google Sheets OAuth credential (re-auth)
5. Import `ID8_PB-Attio_webhook.json`
6. Activate all workflows, copy Production webhook URLs

### Phase 6 — Apps Script (Oscar)

1. script.google.com → New project
2. Paste `drive-watcher.gs`, set `N8N_BASE` to n8n URL
3. Run `installTriggers()` once

---

## 6. Monthly Cost Breakdown

| Service | Config | $/mo |
|---|---|---|
| n8n Cloud Run | 1 vCPU / 1Gi, min=1, CPU throttled | ~$9 |
| app.py Cloud Run | 1 vCPU / 512Mi, min=0 | ~$1 |
| Neon Postgres | Free tier | $0 |
| Artifact Registry | 2 images, ~2GB | ~$0.10 |
| Secret Manager | 3 secrets | ~$0.10 |
| Apps Script | Free | $0 |
| RSS / EDGAR / GDELT | Free | $0 |
| **Total** | | **~$10-11/mo** |

---

## 7. IAM Roles Required (Oscar's account)

To be granted by the GCP project owner (boss):

| Role | Purpose |
|---|---|
| `roles/run.admin` | Deploy and manage Cloud Run services |
| `roles/artifactregistry.admin` | Push Docker images |
| `roles/secretmanager.admin` | Create and update secrets |
| `roles/cloudbuild.builds.editor` | Submit builds via Cloud Build |
| `roles/iam.serviceAccountUser` | Allow deploying as the compute service account |
| `roles/logging.viewer` | Read Cloud Run logs for debugging |

---

## 8. Capabilities Summary

With this stack fully deployed, the firm has:

- **Automated deal ingestion** — PitchBook, Watchlist, Top 10 VC drops processed within minutes of file landing in Drive
- **Jesse's deal submission** — sheet edits trigger automatic Attio sync
- **RSS/SEC intelligence workflows** — infrastructure ready to add deal digest, portfolio monitoring, LP intelligence, and competitive radar without any structural changes
- **Scalable orchestration** — n8n canvas for adding new workflows without code changes
- **Full audit trail** — n8n execution history in Neon, all writes logged in Attio
