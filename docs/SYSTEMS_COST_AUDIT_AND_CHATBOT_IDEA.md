# ID8 Investments — Infrastructure Audit & Monthly Cost Estimate

**Prepared by:** Oscar Varas
**Date:** July 2026 (supersedes the July 8 draft below the fold — several things shipped or changed since)

> Cost figures are estimated from public list pricing plus the actual-billing notes already
> logged in this repo's own deploy scripts (no GCP billing console access from this tool).
> Treat dollar figures as planning-grade ranges, not invoiced amounts. Sources linked at the bottom.
> Status tags follow a 3-tier model: **Live** (running in production, evidence cited), **Built /
> partial** (real code, deployment or end-to-end use unverified from here), **Planned** (not started).

---

## 1. What's running now (Live)

| Service | What it does | Where | Evidence |
|---|---|---|---|
| **n8n** | Automation engine — PitchBook/Watchlist/Top-10-VC/Jesse's-Deals intake workflows, Google Drive/Sheets polling triggers | Cloud Run `us-east4`, `--min-instances=1` (always-on for polling), **IAP-gated** (Google sign-in required, allowlist = `oscar@id8investments.com`) | [n8n-cloudrun/deploy.sh](../n8n-cloudrun/deploy.sh), commit `6b4904c` |
| **id8 pipeline** (Flask `app.py`) | PitchBook↔Attio writes, Apollo Reach Out, Deal Intelligence Stage 1 fit-scoring, and the new Research Chat backend | Cloud Run `us-east4`, scale-to-zero | root [Dockerfile](../Dockerfile), [pipeline/app.py](../pipeline/app.py) |
| **hub-next** | Internal hub — Deal Summaries / Watchlist / Pipeline / Qualified Deals tabs, Top 10 VCs, Market Map, Attio bulk import, Research Chat UI | Cloud Run `us-central1`, `--allow-unauthenticated` at the Cloud Run layer (app-level NextAuth gate instead — internal auto-approved, outside investors manually approved) | [hub-next/cloudbuild.yaml](../hub-next/cloudbuild.yaml) |
| **hub** (legacy Docusaurus) | The original static research/capabilities site — now largely superseded by hub-next | Cloud Run `us-central1`, IAM-private + server-side Firebase session-cookie gate | [hub/cloudbuild.yaml](../hub/cloudbuild.yaml) |
| **cc-attio-sync** | Attio list membership → Constant Contact sync, delete/GDPR endpoint, list-reconcile endpoint | Cloud Run `us-east4` (fully private — org policy blocks public Cloud Run, see below), fronted by **API Gateway** for the public webhook | [cc-attio-sync/deploy.sh](../cc-attio-sync/deploy.sh) |
| **Gmail → Attio intro sync** | Logs intro emails (e.g. Michael Hughes) into Attio | Google Apps Script — free, runs on Google's servers | [gmail-attio-scripts/michael-hughes-intro-sync.gs](../gmail-attio-scripts/michael-hughes-intro-sync.gs) |
| **Cloud SQL** (`n8n-db`) | n8n's own workflow/credential/execution-history store (control-plane data only, no deal data) | `db-f1-micro`, execution history pruned to 14 days / 10k rows | deploy.sh header |
| **Firestore** (default database) | `deal_intelligence`'s Stage-1 write path, hub-next's app data (companies, ideas, market map, top VCs, deal decks), `cc_sync_log` audit trail | Shared across 3 services, one project | multiple `firestore_push.py`, `hub-next/src/lib/*.js` |
| **Cloud Storage** (2 buckets) | Deal-summary `.docx` output (`DI_DOCX_BUCKET`) + Market Map images (`MARKET_MAP_BUCKET`) | `us-central1`/`us-east4` | hub-next `cloudbuild.yaml` substitutions |
| **Artifact Registry** | Docker images for n8n, id8 pipeline, hub, hub-next (cc-attio-sync deploys `--source .` directly, no separate repo) | ~4 repos | respective deploy configs |
| **Secret Manager** | ~10 secrets across the 5 services above (encryption keys, DB password, OAuth secrets, Attio/Perplexity/CC API keys, webhook secret) | | |

A GCP **org policy (Domain Restricted Sharing)** blocks `allUsers`/`--allow-unauthenticated` from ever binding on this project — nobody holds org-admin to change it. Every service above that needs to be reachable by something outside the project either lives behind **IAP** (n8n) or **API Gateway** (cc-attio-sync), or relies on its own app-level auth (hub-next, hub). See [project_gcp_org_policy_blocks_public_cloud_run](internal note) for the mechanics — not fixable without someone claiming org-policy-admin rights.

---

## 2. Built but not fully proven (real code, deployment/usage unverified)

- **n8n's IAP lockdown is committed in code** (`6b4904c`, fixing the "n8n fully public with no app auth" exposure flagged in the 07-14 security audit) — but I can't confirm from here whether `./deploy.sh` has actually been re-run against the live Cloud Run service. Confirm the service is really IAP-gated before treating that exposure as closed.
- **Research Chat** — this *is* last cycle's "chatbot in the hub" idea, now actually built: a chat panel in hub-next (`ResearchChat.jsx`) that POSTs to the pipeline's `/research-chat` endpoint, parses a free-text ask into a company + context, and runs either a Stage 1 (Perplexity-only) or Stage 2 (Perplexity + Anthropic synthesis) investigation on demand. Real and wired end-to-end; usage is ad hoc, so its AI cost isn't a fixed line item, it scales with how often people use it.
- **Deal Intelligence Stage 2** (deep research + memo synthesis via Anthropic) — real code, still not the default path for the weekly Stage 1 screen (`stage1_only=True` there); it runs when Research Chat or the memo/deal-summary skills are invoked directly.
- **Attio write-back** for Deal Intelligence scores (`fit_score`, `fit_gate`, `fit_rationale`, `hub_url`, `memo_url`, `final_score`) is still a no-op — the Attio fields themselves were never created (`deal_intelligence/config.py` `WRITE_SLUGS`, all `TODO`).
- **cc-attio-sync's `/reconcile`** endpoint (removes contacts from Constant Contact when they fall off an Attio list) is built and `py_compile`-checked but not yet exercised live; it also still needs a Cloud Scheduler cron job pointed at it, which doesn't exist yet.
- **hub-next's investor-approval path** — the two-tier access model (internal auto-approve / outside investor manual-approve into a scoped `/investors/research` page) is built and code-reviewed, but only the internal path has been tested with a real Google account so far.

---

## 3. Planned / not started ("will run" — nothing here has cost yet)

- **Carta API → Attio LP sync** — poll Carta's List Partners endpoint for newly-signed LPs and push them to Attio, mirroring the Gmail-intro-sync pattern. Blocked on confirming ID8's Carta plan actually includes API access.
- **Apollo Search API programmatic list-building** — every LP/lead list today starts from a CSV a human exports from Apollo's UI; querying Apollo's database directly (the actual "chatbot builds me a filtered Apollo list" ask) doesn't exist yet.
- **External investor-facing dashboard** (deal summaries + company list + sourcing narrative, modeled on the Nvidia-facing pipeline deck) — deliberately deferred by team agreement; the access-control plumbing exists, the actual dashboard content doesn't.
- **Public-stocks memo template** — a separate analytical template for public names — deferred, prioritized behind the hub tab work.
- **Proprietary research-context/intelligence layer** (accumulating pass/invest rationale over time) — discussed, explicitly not scoped or started; too time-consuming to write up per-deal right now.
- **Weekly Cloud Scheduler → Cloud Build rebuild** for the hub — documented as the plan in `hub/README.md` and `MIGRATION_RUNBOOK.md`, no evidence it's actually been created.

None of these carry any infrastructure cost today — they're either free-tier polling scripts (Carta, same shape as the Gmail sync) or pure application work riding on infrastructure already paid for below.

---

## 4. One live risk worth flagging (cost-adjacent, not just security)

`lp-screener/perplexity_lp_screener.py` has a **hardcoded, live Perplexity API key** committed in git history since `3e4e9d5` — still present in `HEAD` today. A fix (reading it from `os.getenv` instead) exists but is sitting **uncommitted** in the working tree right now. Until it's committed *and* the key is rotated, anyone with repo access (this pushes to `github.com/ocachin/id8-intelligence`) can run up Perplexity charges on that key, or worse. Recommend: commit the pending fix, rotate the key in Perplexity's console, and update `deal_intelligence/.env` to match.

---

## 5. Monthly cost estimate

### 5a. Infrastructure (incremental cash cost — what ID8 built)

| Item | Est. $/mo | Basis |
|---|---|---|
| n8n (Cloud Run + Cloud SQL `db-f1-micro`, IAP) | **~$26–28** | `deploy.sh`'s own header, quoting actual Jul 2026 billing (Cloud SQL ~$9 + Cloud Run ~$17 + Artifact Registry/Secret Manager ~$2) — the most reliable figure in this table since it's not a public-pricing guess |
| id8 pipeline / Flask (Cloud Run, scale-to-zero) | ~$1–3 | [Cloud Run pricing](https://cloud.google.com/run/pricing) — 2M free requests/mo, low invocation count, occasional long-running Stage-1 sonar-deep-research calls |
| hub-next (Cloud Run, scale-to-zero) | ~$1–5 | same pricing page; Next.js SSR, internal team + a handful of approved investors |
| hub — legacy Docusaurus (Cloud Run, scale-to-zero) | ~$0–2 | same; candidate to retire now that hub-next covers the same ground |
| cc-attio-sync (Cloud Run, `max-instances=1`, scale-to-zero) | ~$0–1 | low webhook volume |
| API Gateway (cc-attio-sync public front door) | ~$0 | [API Gateway pricing](https://apigatewaycost.com/google-cloud) — 2M calls/mo free, then $3/million; nowhere close at ID8's volume |
| Firestore (shared default database, 3 services) | ~$0–1 | [Firestore pricing](https://cloud.google.com/firestore/pricing) — free tier is 50K reads/20K writes/20K deletes per day + 1 GiB storage |
| Cloud Storage (2 buckets: deal-summary docs + market-map images) | ~$0–1 | [Cloud Storage pricing](https://cloud.google.com/storage/pricing) — $0.02/GB-mo standard, low object count |
| Artifact Registry (4 image repos) | ~$0.30–0.50 | image storage |
| Secret Manager (~10 secrets across 5 services) | ~$0.30–0.50 | per-secret-version pricing |
| **Subtotal** | **~$30–42/mo** | |

### 5b. AI/API usage (pay-as-you-go, scales with volume)

| Item | Est. $/mo | Notes |
|---|---|---|
| Perplexity API (LP enrichment, Deal Intel Stage 1, Research Chat Stage 1) | ~$3–10 | Sonar models run $1–5/1M tokens + a per-1,000-request search fee; Stage 1 now runs `sonar-deep-research` at max reasoning effort (pricier per call), plus new ad hoc Research Chat usage on top of the weekly screen |
| Anthropic Claude API (Deal Intel Stage 2, memo/deal-summary skill generation, Research Chat Stage 2) | ~$15–50 | Sonnet-class pricing ~$2–3/1M input, ~$10–15/1M output; a single memo's multi-agent generation runs low single digits in tokens — real cost is a function of how many memos/deep dives run per month, not a fixed rate |
| **Subtotal** | **~$18–60/mo** | |

**Infra + AI total: ~$48–102/mo** — wider and somewhat higher than the July 8 estimate (~$39–76/mo), mainly because hub-next now runs as its own Cloud Run service with Firestore + two GCS buckets, and Research Chat adds a genuinely new, usage-scaling AI cost line that didn't exist two weeks ago.

### 5c. Existing firm subscriptions (not incremental — the fund pays these regardless of any automation)

| Item | Estimated cost | Notes |
|---|---|---|
| PitchBook | ~$1,250–2,500+/mo ($15K–30K+/yr) | No public pricing; industry-reported range for a small-seat VC subscription — the dominant line item by a wide margin |
| Attio | ~$60–350/mo | Plus tier ~$29–36/user/mo, Pro ~$69–86/user/mo depending on seat count/tier |
| Apollo.io | ~$50–240/mo | Basic ~$49/user/mo up to Organization ~$119/user/mo, per-seat |
| Constant Contact | ~$12–80/mo | Scales with list size; ID8's FO/RIA lists are small, likely the low end |
| Carta (fund administration) | Existing, not itemized | Fund-admin platform ID8 already pays for; no automation touches it yet (the Carta→Attio LP sync in §3 is still just planned) |
| Google Workspace | Existing, not itemized | Cost of doing business regardless of this stack |

**Grand total, everything: roughly $1,450–3,300+/mo** — the automation/AI stack Oscar built and runs is only **~$48–102/mo of that, or about 2–4%**. PitchBook alone still costs on the order of 15–50x what the entire automation layer costs to run.

---

## Sources

- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Cloud Firestore pricing](https://cloud.google.com/firestore/pricing)
- [Cloud Storage pricing](https://cloud.google.com/storage/pricing)
- [API Gateway pricing (Google Cloud)](https://apigatewaycost.com/google-cloud)
- [Attio pricing](https://attio.com/pricing) · [Attio CRM Pricing 2026 breakdown](https://marketbetter.ai/blog/attio-crm-pricing-breakdown-2026/)
- [Apollo.io pricing](https://www.apollo.io/pricing) · [Apollo Pricing 2026 breakdown](https://www.warmly.ai/p/blog/apollo-pricing)
- [Perplexity API pricing](https://docs.perplexity.ai/docs/getting-started/pricing)
- [Anthropic Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Constant Contact pricing](https://www.constantcontact.com/pricing)
- [PitchBook pricing (Vendr transaction data)](https://www.vendr.com/marketplace/pitchbook) · [PitchBook Pricing 2026 breakdown](https://www.startupyeti.com/startup/the-cost-of-pitchbook)
- In-repo: [n8n-cloudrun/deploy.sh](../n8n-cloudrun/deploy.sh) (actual Jul 2026 billing quoted in header), [n8n-cloudrun/TECHNICAL_SPEC.md](../n8n-cloudrun/TECHNICAL_SPEC.md), [cc-attio-sync/deploy.sh](../cc-attio-sync/deploy.sh), [hub-next/cloudbuild.yaml](../hub-next/cloudbuild.yaml), [hub/cloudbuild.yaml](../hub/cloudbuild.yaml)
