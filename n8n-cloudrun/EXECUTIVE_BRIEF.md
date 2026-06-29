# ID8 Intelligence Pipeline — Executive Brief

**Prepared by:** Oscar Varas  
**Date:** June 2026

---

## What We're Building

A private, automated market intelligence and deal management system that runs on
Google's cloud infrastructure. It replaces manual processes — downloading files,
copy-pasting into spreadsheets, searching for news — with a system that does it
automatically and notifies the team when something relevant surfaces.

Everything runs under ID8's own cloud account. No vendor lock-in. No third-party
platform holding our data.

---

## What It Does

**Today (already works locally, being moved to cloud):**
- Processes PitchBook weekly exports automatically — companies land in Attio within minutes of the file being dropped in Google Drive
- Manages the Watchlist and Top 10 VC deal tracking the same way
- Picks up Jesse's deal submissions from a Google Sheet and pushes them to Attio

**Ready to add (infrastructure supports it, not in initial scope):**
- **Morning deal digest** — scan 15+ financial news sources daily, filter by sector/stage, email a curated summary
- **Portfolio company monitoring** — automatically track news mentions of companies we're watching and log them in Attio
- **LP intelligence** — weekly SEC filing scan to flag when target family offices or RIAs make new fund commitments
- **Competitive radar** — weekly summary of what the top VC firms are actively backing

---

## Why Google Cloud Run (Not a SaaS Platform)

Most workflow automation tools (Zapier, Make, n8n Cloud) charge $50–300/mo and
hold your data and credentials on their servers. Running this on Google Cloud Run means:

- **Our data stays ours** — credentials, workflow logic, and deal data never leave Google's infrastructure
- **Cost is fixed and low** — we pay for compute, not per-task pricing that scales with volume
- **Full control** — we can add any capability without hitting platform limits or upgrading plans
- **Same infrastructure** — runs in the same Google Cloud account as everything else

---

## Monthly Cost: ~$12-14

| What | Cost |
|---|---|
| Automation engine (n8n on Google Cloud) | ~$9/mo |
| Data pipeline server (Python app) | ~$1/mo |
| Database, storage, secrets | ~$0.20/mo |
| News, SEC, and market data feeds | $0 (free public APIs) |
| **Total** | **~$10-11/mo** |

For context: a single Zapier Business plan is $69/mo and couldn't do half of this.

---

## What We Need to Get Started

1. **A Google Cloud project** with billing enabled — this can be under the firm's Google account or a dedicated project account. Oscar will handle all technical setup once access is granted.

2. **Perplexity API account** — the AI service used for summarizing news. Free to sign up, pay-as-you-go (~$2-3/mo at our usage).

3. **Neon account** — free database service that stores the automation system's configuration. Takes 5 minutes to set up.

That's it. No new hardware. No server management. Everything runs on Google's infrastructure and scales automatically.

---

## Timeline

| Phase | What | Who | Time |
|---|---|---|---|
| 1 | GCP project setup + grant access | Account owner | 30 min |
| 2 | Deploy automation engine (n8n) | Oscar | 1–2 hours |
| 3 | Deploy data pipeline + re-auth credentials | Oscar | 1 hour |
| 4 | Build intelligence workflows (⑤–⑧) | Oscar | 2–3 hours |
| 5 | Test end-to-end, cut over from local | Oscar | 1 hour |

**Total elapsed time to fully operational: 1–2 days.**

---

## Risk / Downside

- **If Google Cloud goes down:** Google Cloud Run has 99.95% SLA. In the rare event of downtime, PitchBook files queue in Drive and process when the service recovers. No data is lost.
- **If n8n has a bug:** Execution logs are preserved in the database. Every run is auditable and replayable.
- **Ongoing maintenance:** Essentially none. The system is event-driven — it runs when something happens and stays quiet otherwise. Docker image updates take one command.
