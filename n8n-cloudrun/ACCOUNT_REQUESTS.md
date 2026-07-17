# Account & Access Requests

**Prepared by:** Oscar Varas  
**For:** [Account owner / boss]  
**Purpose:** Everything needed before Oscar can deploy the pipeline

> **⚠️ Update (Jul 2026):** This was written before the project existed; the
> actual project is `molten-crowbar-498920-q8` (`137750788450`), not
> `id8-pipeline`. §4 (Neon account) never happened — the DB is Cloud SQL
> Postgres, created and billed inside this same GCP project, so there's no
> separate Neon signup/account to track.

---

## 1. Google Cloud Project

**What:** A GCP project to host all cloud services.

**Options (pick one):**

| Option | Recommendation | Notes |
|---|---|---|
| New dedicated project under firm's Google account | ✅ Preferred | Clean separation, firm owns billing, easy to add team members later |
| Sub-project under existing GCP organization | ✅ Also fine | If the firm already has a GCP org, just create a new project inside it |
| Oscar's personal GCP account | ❌ Avoid | Infrastructure shouldn't be tied to an employee's personal account |

**Actions needed from account owner:**

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project — suggested name: **`id8-pipeline`**
3. Link a billing account (Google Cloud gives $300 free credit for new accounts — more than enough to test everything before any real charges)
4. Share the **Project ID** with Oscar (looks like `id8-pipeline-123456`)

---

## 2. IAM Access for Oscar

**What:** Permissions so Oscar can deploy services without needing the account owner for every step.

**How:** In GCP Console → IAM & Admin → IAM → Grant Access

| Grant to | Email | Role |
|---|---|---|
| Oscar | oscar@id8investments.com | **Owner** |

**Why Owner:** Simplest option for an internal project. Owner covers all the permissions needed to deploy Cloud Run services, push Docker images, manage secrets, and read logs — with no risk of hitting a permission error mid-deploy.

**What Owner can do** (so the account owner is aware): full control of the project including deleting it, adding/removing other users, and viewing all resources. It cannot access billing settings or other GCP projects. For a dedicated internal project like this, Owner is the standard choice.

---

## 3. OAuth Consent Screen (for Google Drive + Gmail integration)

**What:** Allows the n8n automation to connect to Google Drive (to download PitchBook files) and Gmail (to send digest emails) using OAuth — the same "Sign in with Google" flow used by any app.

**How:** In GCP Console → APIs & Services → OAuth consent screen

**Settings to configure:**

| Field | Value |
|---|---|
| User type | **Internal** (only accounts in your Google Workspace domain can authorize) |
| App name | `ID8 Pipeline` |
| User support email | oscar@id8investments.com |
| Developer contact | oscar@id8investments.com |
| Scopes | Oscar will add these during n8n credential setup — no action needed here |

**Important:** After Oscar deploys n8n and gets its URL, the account owner needs to add one Authorized Redirect URI:

```
https://n8n-[hash].us-east4.run.app/rest/oauth2-credential/callback
```

Oscar will provide the exact URL after the first deploy. This is a one-time step that takes about 2 minutes.

---

## 4. Neon Account (free — no billing needed)

**What:** A free serverless database that stores n8n's configuration, credentials, and workflow execution history.

**Who should own it:** Oscar can set this up independently. No credit card required on the free tier.

**Steps:**
1. Oscar goes to [neon.tech](https://neon.tech)
2. Signs up with work email
3. Creates a project
4. Copies the connection string into Secret Manager

No action needed from account owner.

---

## 6. Google Apps Script (no new account needed)

**What:** The Google-native scripting environment that watches Drive folders and triggers the pipeline. Runs free inside Google's infrastructure.

**Who runs it:** Oscar deploys this under the Google account that has access to the PitchBook/Watchlist/Top10 Drive folders and Jesse's Deals spreadsheet.

**No action needed from account owner** — unless the Drive folders are owned by a different account, in which case Oscar needs view/read access to those specific folders.

---

## Summary Checklist for Account Owner

- [ ] Create GCP project `id8-pipeline` with billing enabled
- [ ] Grant Oscar **Owner** role on the project (IAM & Admin → IAM → Grant Access)
- [ ] Configure OAuth consent screen (Internal, App name: "ID8 Pipeline")
- [ ] After Oscar's first deploy: add the n8n redirect URI to OAuth client (Oscar provides the URL)

**Total time required from account owner: ~45 minutes, mostly one-time setup.**

After that, Oscar handles all deployments, updates, and maintenance independently.
