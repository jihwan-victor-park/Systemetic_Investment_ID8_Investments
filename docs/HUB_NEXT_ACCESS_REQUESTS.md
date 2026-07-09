# hub-next — Access & Setup Requests

**Purpose:** Everything still needed to take hub-next from "Oscar can see it via a proxy trick" to "the whole ID8 team can just open a link." Written the same way as `n8n-cloudrun/ACCOUNT_REQUESTS.md` — that one got the original GCP project stood up; this one finishes the hub.

---

## Already in place — don't re-request these

- ✅ Oscar has **Owner** on the GCP project (`molten-crowbar-498920-q8`)
- ✅ OAuth consent screen already exists (Internal, app name "ID8 Pipeline") — set up originally for n8n's Drive/Gmail OAuth
- ✅ Firestore database, the `molten-crowbar-498920-q8-hub-next-docs` Cloud Storage bucket, and the IAM roles the `id8` pipeline needs to write to both — all self-serviced by Oscar today, no external grant needed
- ✅ `hub-next` is deployed and running (`id8-hub-next` on Cloud Run, `us-central1`)
- ✅ `roles/run.invoker` granted to `oscar@id8investments.com` directly — proven working (curl + `gcloud run services proxy` both succeed)

## What's blocking "just open a link" today

Plain Cloud Run access control (`roles/run.invoker`) has no browser sign-in flow — only **Identity-Aware Proxy (IAP)** provides that. IAP was never set up, for either hub-next or the old hub. That's the actual gap, not a permissions problem Oscar is missing.

## New requests, grouped by who can grant them

### 1. Things Oscar can do himself (already has GCP Owner)
- [ ] Enable the IAP API on the project
- [ ] Turn on IAP for the `id8-hub-next` Cloud Run service
- [ ] Grant `roles/iap.httpsResourceAccessor` to whoever needs access (same mechanism already proven with his own account)

### 2. Needs Google Workspace Admin console access (admin.google.com — separate system from GCP IAM; may or may not be a different person than "GCP project owner")
- [ ] Create a group (e.g. `team@id8investments.com`) so access is granted once to the group, not one person at a time as the team grows
- [ ] Confirm the existing "Internal" OAuth consent screen designation covers IAP, or re-approve it if IAP requires a fresh look

### 3. Needs DNS control for id8investments.com (registrar or DNS provider — another separate system)
- [ ] Optional: a CNAME/verification record to map `intel.id8investments.com` (or similar) to the Cloud Run service, instead of the `.run.app` URL. Cosmetic only — everything works on the default URL without this.

### 4. Cost awareness for whoever owns billing
- IAP itself: no additional cost
- If IAP requires the older-style External HTTPS Load Balancer path (rather than direct-on-Cloud-Run IAP) to support the custom domain: adds a small reserved-IP + load-balancer cost, roughly $18–25/mo — confirm which path applies before assuming this
- Firestore/GCS/hub-next Cloud Run: already within existing footprint, no new material cost

## Not a request — leave this alone

- The **Domain Restricted Sharing** org policy (blocks `allUsers`/public access) is not something to ask to change. IAP scoped to `@id8investments.com` works fine within it — no exception needed, and loosening it would remove a real security guardrail for no benefit here.

## Also still true from the earlier systems audit, unrelated to hub-next specifically
- The **old hub** (Docusaurus, `id8-cloud-intelligence` service) is currently live and fully **unauthenticated** in production — a real, pre-existing exposure. Worth deciding whether to retire it or lock it down at the same time as this work, rather than leaving two hubs in inconsistent security states.
