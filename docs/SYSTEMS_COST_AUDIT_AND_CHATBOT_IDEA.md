# ID8 Investments — Systems Cost Audit & Hub Chatbot Idea

**Prepared by:** Oscar Varas
**Date:** July 2026

> Cost figures below are estimated from public list pricing and the usage patterns described in each
> system's own docs/code — not pulled from actual billing consoles (no console access from this tool).
> Treat dollar figures as planning-grade ranges, not invoiced amounts. Sources are linked at the bottom.

---

## 1. What's already built, and what it's saving

| System | Replaces (manual process) | Status | Estimated time saved |
|---|---|---|---|
| PitchBook → Attio Pipeline | Downloading weekly PitchBook/Watchlist/Top-10-VC exports and hand-entering deals, companies, and investor links into Attio | Live | ~3–5 hrs/week |
| Jesse's Deal Intake | Checking a Google Sheet and re-keying submissions into Attio | Live | ~30–60 min/week |
| Apollo Reach Out | Manually filtering Apollo's database, researching each FO/RIA contact, and scoring LP fit by hand | Live | ~8–15 hrs per outbound campaign (was a multi-day list-building task, now a filtered pull + automated Perplexity enrichment) |
| Attio → Constant Contact sync | Exporting an Attio list to CSV and re-importing it into Constant Contact per campaign | Live | ~20–30 min per list add |
| Deal Intelligence — Stage 1 fit scoring | Reading every qualified deal's materials and scoring it against the rubric by hand | Live | ~15–30 min per deal |
| Deal Intelligence — Stage 2 research + memo | Deep-diving and writing the fit rationale for deals that clear the gate | In build | Multi-hour research task → target ~30–60 min review once live |
| Investment Memo / Deal Summary skills | Drafting a full IC memo or one-pager from scratch | Live (skills), used ad hoc | Multi-day writing task → ~1–2 hrs (generation + edit pass) |
| Gmail → Attio intro sync | Manually logging intro emails (e.g. Michael Hughes) into Attio | Live | ~10–15 min per intro |

These are modeled from what each system replaces, not logged time-tracking data — worth sanity-checking against your own sense of how long these actually took manually.

---

## 2. Full cost of deploying everything

Everything is self-built on Google Cloud Run and Google Workspace, both of which have generous free tiers at this
traffic level. There's no licensing fee, no platform setup fee, and the custom domain (`intel.id8investments.com`
or similar) is a subdomain of a domain ID8 already owns.

**One-time cash cost: effectively $0.** The real one-time cost is build time, already logged in the existing
[Executive Brief](../n8n-cloudrun/EXECUTIVE_BRIEF.md): ~1–2 days to get the live systems fully operational, plus
2–3 hours per additional workflow layered on afterward. That's Oscar's time, not a cash outlay.

---

## 3. Monthly cost of everything

### 3a. New infrastructure ID8 built (incremental cash cost)

| Item | Cost | Source |
|---|---|---|
| n8n automation engine (Cloud Run) | ~$8–10/mo | [n8n-cloudrun/TECHNICAL_SPEC.md](../n8n-cloudrun/TECHNICAL_SPEC.md) |
| Data pipeline (Flask app.py — PitchBook↔Attio, Apollo sync, Deal Intelligence orchestration) | ~$0–1/mo | same |
| Hub (Docusaurus, Cloud Run + Firebase Hosting rewrite) | ~$1–2/mo | estimated, same class of service |
| Attio → Constant Contact sync (`cc-attio-sync`, max-instances 1, low volume) | ~$0–1/mo | estimated from [cc-attio-sync/README.md](../cc-attio-sync/README.md) |
| Neon Postgres (n8n config/run history) | $0/mo | free tier |
| Artifact Registry (Docker images, 4 services) | ~$0.20–0.40/mo | estimated |
| Secret Manager (API keys/tokens) | ~$0.10–0.30/mo | estimated |
| Custom domain | $0 | subdomain of existing domain |
| **Subtotal** | **~$10–15/mo** | |

### 3b. AI usage (pay-as-you-go, scales with volume)

| Item | Cost | Notes |
|---|---|---|
| Perplexity API (LP enrichment, deal fit research, news) | ~$2–5/mo at current volume | Sonar models run $1–5/1M tokens plus a $5–14 per-1,000-request search fee; light usage today, scales with deal/LP volume |
| Anthropic Claude (Deal Intelligence stage 2, memo/deal-summary generation) | ~$10–40/mo estimated | Sonnet-class pricing is ~$2–3/1M input, ~$10–15/1M output; a single memo's multi-agent generation runs low single-digit dollars in tokens — cost is really a function of how many memos/deep-research passes run per month |
| **Subtotal** | **~$12–45/mo** | |

**New infrastructure + AI total: ~$22–60/mo.**

### 3c. Existing firm subscriptions (not incremental — the fund pays these regardless of any automation)

| Item | Estimated cost | Notes |
|---|---|---|
| PitchBook | ~$1,250–2,500+/mo ($15K–30K+/yr) | No public pricing; industry-reported range for a small-seat VC subscription. This is the dominant line item by a wide margin. |
| Attio | ~$60–350/mo | Plus tier ~$29–36/user/mo, Pro ~$69–86/user/mo; depends on seat count and tier (Pro likely needed for the custom objects/write-back fields this automation uses) |
| Apollo.io | ~$50–240/mo | Basic ~$49/user/mo up to Organization ~$119/user/mo, per-seat |
| Constant Contact | ~$12–80/mo | Scales with list size; ID8's FO/RIA lists are small (tens to low hundreds of contacts), so likely the low end |
| Google Workspace | Existing, not itemized | Cost of doing business regardless of this stack |

**Grand total, everything: roughly $1,400–3,200+/mo** — and the automation/AI stack Oscar built is only
**~$25–60/mo of that, or about 2–4%**. The rest is data/CRM/outbound subscriptions the fund pays whether or not
any of this automation exists. The honest framing: PitchBook alone costs 100–250x what the entire automation
layer costs to run.

---

## 4. New idea: a chatbot in the hub

A chat panel inside the hub — type a plain-English request and it calls the scripts and skills already built,
instead of Oscar opening a terminal and running each one by hand. "Write a deal summary for X." "Run stage-1
scoring on this week's PitchBook batch." "Pull FO prospects in Texas that match the LP rubric." The chatbot
routes the request to the right existing tool (`investment-memo`, `deal-summary`, `deal_intelligence.pipeline`,
the LP screener) and hands back the result — a docx link, a scored list, a fit rationale — right in the chat.

**Why it's cheap to build:** every hard part already exists and is deployed — the memo-writing logic, the
scoring rubric, the Attio/PitchBook/Perplexity/Anthropic integrations. The chatbot itself is a thin orchestration
layer: an agent with tool-calling access that picks the right script and runs it. No new data pipelines, no new
subscriptions — it rides on the same Cloud Run + Anthropic API infrastructure already paid for above.

**Why it keeps paying off:** because each capability is exposed as one callable tool, adding the next one is
"write a script, register it as a tool" — the same incremental pattern that let Deal Intelligence ride on the
n8n infrastructure already deployed for Apollo Reach Out. Whatever the next intelligence workflow is, extending
the chatbot to cover it is a few hours of work, not a new system.

**Rough cost/effort:** build effort is roughly 1–2 days given the underlying tools already exist. Marginal
running cost is a few cents to a few dollars in Anthropic tokens per conversation — it folds into the existing
AI-usage line in §3b, no new monthly line item.

---

## Sources

- [Attio pricing](https://attio.com/pricing) · [Attio CRM Pricing 2026 breakdown](https://marketbetter.ai/blog/attio-crm-pricing-breakdown-2026/)
- [Apollo.io pricing](https://www.apollo.io/pricing) · [Apollo Pricing 2026 breakdown](https://www.warmly.ai/p/blog/apollo-pricing)
- [Perplexity API pricing](https://docs.perplexity.ai/docs/getting-started/pricing)
- [Anthropic Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Constant Contact pricing](https://www.constantcontact.com/pricing)
- [PitchBook pricing (Vendr transaction data)](https://www.vendr.com/marketplace/pitchbook) · [PitchBook Pricing 2026 breakdown](https://www.startupyeti.com/startup/the-cost-of-pitchbook)
