# ID8 Investments — AI & Automation Capabilities

**One-pager: what's live, what's next, and what it costs**

**Prepared by:** Oscar Varas
**Date:** June 2026

---

## The Idea

ID8 runs a set of AI and automation systems that turn raw market data into fund workflows — replacing manual file-handling, list-building, and research with systems that run themselves and notify the team when something matters. Three layers, each compounding the others:

| Layer | Role |
|---|---|
| PitchBook → Attio Pipeline | The CRM layer — keeps deal, company, and investor data accurate |
| Apollo Reach Out | The outbound layer — builds and enriches LP/prospect lists |
| Deal Intelligence | The proprietary layer — scores and researches every deal against ID8's rubric |

Everything runs on ID8's own Google Cloud infrastructure. No vendor lock-in, no third party holding fund data or credentials.

---

## Already Built (Live)

| System | What It Does | Status |
|---|---|---|
| PitchBook → Attio Pipeline | Processes weekly PitchBook exports, the Watchlist, and Top 10 VC drops — deals and companies land in Attio within minutes, investor links resolved automatically | Live |
| Jesse's Deal Intake | Picks up deal submissions from a Google Sheet and pushes them to Attio | Live |
| Apollo Reach Out | Filters Apollo's database down to clean family office / RIA decision-maker lists, enriches each with Perplexity research and an LP fit score, loads qualified contacts into outbound sequences | Live |

---

## In Build / Coming Next

| System | What It Does | Stage |
|---|---|---|
| Deal Intelligence | Two-stage AI scoring — a fast fit check on every qualified deal, then deep multi-angle research and a synthesized memo on the ones that clear the bar | In build |
| Morning Deal Digest | Scans 15+ financial news sources daily, filters by sector/stage, emails a curated summary | Ready to add |
| Portfolio Company Monitoring | Tracks news mentions of portfolio and watchlist companies, logs them on the Attio record | Ready to add |
| LP Intelligence | Weekly SEC 13F filing scan to flag when target family offices/RIAs make new fund commitments | Ready to add |
| Competitive VC Radar | Weekly summary of what the top VC firms in our network are actively backing | Ready to add |

"Ready to add" systems ride on the infrastructure already deployed for the live systems above — adding them is build time (hours), not new monthly cost.

Phase 2 roadmap (documented, not yet built): **Thesis Radar** — a broader signal aggregator (web pages, hiring, filings, product launches) scored against ID8's investment theses.

---

## Platforms In Use

| Platform | Role | Status |
|---|---|---|
| Attio | Fund CRM — deals, companies, LPs | Existing subscription |
| Apollo | Outbound contact database & sequencing | Existing subscription |
| PitchBook | Deal and investor data source | Existing subscription |
| Perplexity | AI research for LP enrichment & news summarization | Pay-as-you-go API |
| Anthropic (Claude) | AI scoring & deep research for Deal Intelligence | Pay-as-you-go API |
| Google Cloud Run | Hosts the automation engine (n8n) and the data pipeline | New — ID8's own infrastructure |
| Neon | Database for automation config and run history | Free tier |
| Google Workspace (Drive / Sheets / Gmail / Apps Script) | Triggers and delivery | Existing, free |

---

## Cost

| Item | Cost |
|---|---|
| Automation engine (n8n, Google Cloud Run) | ~$9/mo |
| Data pipeline server (Python, Cloud Run, scales to zero) | ~$1/mo |
| Database, storage, secrets | ~$0.20/mo |
| AI usage — Perplexity (enrichment, research) | ~$2–3/mo, pay-as-you-go |
| AI usage — Anthropic (deal scoring/research) | Usage-based |
| News, SEC, and market data feeds | $0 — free public APIs |
| **New infrastructure total** | **~$12–15/mo** |

Attio, Apollo, and PitchBook are existing firm subscriptions already paid for CRM, outbound, and sourcing — this build adds automation on top of them at no incremental platform cost. For context, a single Zapier Business plan alone runs $69/mo and can't do half of this.

---

## Timeline

Once GCP access is granted: **1–2 days** to fully operational for the live systems above, plus **2–3 hours per new intelligence workflow** added afterward.
