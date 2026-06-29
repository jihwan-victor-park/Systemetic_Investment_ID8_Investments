# ID8 Investments — Cloud Intelligence Hub
### Build & Deployment Plan

> **Status:** Draft for review — nothing has been built yet.
> **Owner:** Oscar Varas (oscar@id8investments.com)
> **Last updated:** 2026-06-23

---

## 1. What this is

A single private web hub — **ID8 Investments Cloud Intelligence** — that houses every
cloud/automation system the fund runs. It serves two audiences from one source of truth:

- **Internal ("how we do it")** — SOPs, technical structure, repo links, research. Gated, for the team.
- **External ("what we pitch")** — a polished *Capabilities* view that shows LPs and partners the
  infrastructure ID8 operates. Exported as a PDF / standalone page from the same content.

**Design principle:** the docs live next to the code (same repo, versioned, updated via PRs), so the
hub never drifts out of sync with reality. Adding a new project = adding a folder of markdown.

---

## 2. Architecture

| Layer | Choice | Why |
|---|---|---|
| Site framework | **Docusaurus** (static, MDX) | Markdown-native, lives in repo, versioned, easy to extend |
| Hosting | **Cloud Run** (containerized) | Private by default (`--no-allow-unauthenticated`), scales to zero, cheap |
| Auth | **IAP scoped to `@id8investments.com`** | Google-native, no separate auth server, tied to Workspace identities |
| Assets/PDFs | In the image now; **GCS + signed URLs** if they get large | Keep the image small once research grows |
| Domain | Custom domain mapped to the service | e.g. `intel.id8investments.com` |
| CI/CD | **Cloud Build** (or GitHub Actions) → Artifact Registry → Cloud Run | Push to `main` rebuilds and deploys |
| "Alive" refresh | **Weekly scheduled rebuild** (Cloud Scheduler → Cloud Build, or a GitHub Actions cron) | Rebuilds + redeploys weekly so data-driven pages (changelog, Co-Invest Radar signals) refresh on their own |

**Auth simplification:** start with IAP's direct Cloud Run integration scoped to the Workspace domain.
Only fall back to a Cloud Load Balancer in front of IAP if the direct path gives us trouble. This is a
deploy detail, decided at deploy time — not now.

```
GitHub repo  ──push──▶  Cloud Build  ──▶  Artifact Registry  ──▶  Cloud Run (private)
                                                                      ▲
                                                                     IAP  (Google login, @id8investments.com only)
                                                                      ▲
                                                                  custom domain
```

---

## 3. Repository layout

The hub lives in this same repo so docs and pipeline code stay together.

```
id8-pb-attio-pipeline/
├── hub/                         # Docusaurus site
│   ├── docusaurus.config.js
│   ├── sidebars.js
│   ├── docs/
│   │   ├── overview/            # EXTERNAL — the marketable Capabilities view
│   │   ├── projects/
│   │   │   ├── pitchbook-attio/
│   │   │   ├── apollo-reach-out/
│   │   │   └── intelligence/    # Co-Invest Radar (built) + Thesis Radar (planned)
│   │   ├── research/            # uploaded docx/PDF, sector notes, market maps
│   │   └── admin/               # pending ideas, deprecated workflows, data-source access notes
│   ├── static/                  # logos, PDFs (until GCS)
│   ├── Dockerfile
│   └── package.json
├── attio_apollo_sync.py         # existing pipeline code (referenced by docs)
├── perplexity_lp_screener.py
└── ...
```

---

## 4. Site map

```
ID8 Investments Cloud Intelligence
│
├── Home
│   ├── One-line value prop: "A private hub that turns raw market data into fund workflows."
│   ├── Three project cards
│   ├── "What's new" / changelog feed
│   └── Link to Research
│
├── Capabilities  (EXTERNAL — pitch view, exportable to PDF)
│   ├── What ID8 Cloud Intelligence is
│   ├── The three systems, in plain marketing language
│   └── Why it's a moat (proprietary data + workflow automation)
│
├── Projects  (INTERNAL)
│   ├── PitchBook → Attio Pipeline
│   ├── Apollo Reach Out
│   └── Intelligence (Co-Invest Radar + Thesis Radar)
│
├── Research
│   ├── Market maps · Sector notes · Source PDFs · Playbooks · Templates
│
└── Admin / Notes
    ├── Pending ideas · Deprecated workflows · Data sources & access
```

**Every project page uses the same template** so the hub feels systematic:

> Purpose · Inputs · Outputs · Workflow · Technical structure · How to use it · Examples · Limitations · Links to repo & docs

---

## 5. The three projects

### 5.1 PitchBook → Attio Pipeline *(built — document existing system)*
- **Purpose:** Sync PitchBook deal/company/investor data into Attio, with investor reference linking.
- **Code:** `attio_apollo_sync.py`, `app.py`, `attio_import/`.
- **Doc work:** write up purpose, the investor-slug linking rules (lead_investors_8 / new_investors_5),
  write value formats, and the re-import flow.

### 5.2 Apollo Reach Out *(built — document existing system)*
- **Purpose:** Build tightly-filtered FO/RIA decision-maker lists in Apollo, enrich with Perplexity,
  re-import to create the Apollo sequence.
- **Code:** `attio_apollo_sync.py` (`/sync-apollo`), `perplexity_lp_screener.py`, `lp_screener_hybrid.py`.
- **The pre-filtering recipe** (extracted, goes in the docx + page):

  | Filter | Value |
  |---|---|
  | **Include keywords** (Type → ANY) | family office, single family office, multi-family office, private family office, family wealth, private wealth |
  | **Exclude keywords** | bank, banking, brokerage, broker dealer, insurance, asset management, fund administration, hedge fund, private equity, venture capital, real estate, accounting, tax, payroll, fintech, software, technology — plus named wirehouses/platforms: Raymond James, Edward Jones, Morgan Stanley, Wells Fargo, Merrill Lynch, UBS, Fidelity, Vanguard, BlackRock, Charles Schwab, Ameriprise, Northwestern Mutual, LPL Financial |
  | **Employee count** | 1–10 and 11–50 (the single highest-leverage filter — cuts ~90% of platforms) |
  | **Job titles** | Partner, Managing Partner, CIO / Chief Investment Officer, Managing Director, Head of Investments, Director of Investments, Portfolio Manager, Principal, Investment Director |
  | **Seniority** | Owner/Partner, C-Suite, VP, Director |
  | **Location** | Los Angeles (per current LA Trip sequence) |
  | **RIA sub-search** | Keywords "registered investment advisor" OR "RIA"; headcount 1–50; titles Partner, CIO, MD, Principal |

  **Expected funnel:** ~61,889 (broad) → 50–300 clean FO/RIA decision-makers. Visual sanity check: you
  want unfamiliar generic names ("Meridian Family Office"), not recognizable brands.

### 5.3 Intelligence — **Co-Invest Radar** (Phase 1) + **Thesis Radar** (Phase 2)

**Co-Invest Radar (build first — the proprietary wedge):**
- **Why it's a moat:** ID8 is a $50M growth-stage **co-invest** fund. The edge is knowing what the lead
  VCs *already in your network* are doing early enough to ask for allocation. You already store
  `lead_investors` / `new_investors` on every deal in Attio — this turns the CRM into a sourcing engine.
- **What it does:** watches the lead VCs in your Attio pipeline → detects new funds/rounds they're leading
  (PitchBook MCP + web signals) → scores for co-invest fit → produces a short memo + creates a task in Attio.
- **Not in PitchBook** (backward-looking), **not a newsletter** (it's *your* network), compounds data you own.

**Thesis Radar (documented expansion — Phase 2):**
- Broader signal aggregator: web pages, job posts, product launches, funding rumors, hiring changes,
  GitHub activity, filings → scored against ID8 theses → memo/alert.
- Documented now as the roadmap; built after Co-Invest Radar proves out.
- Intelligence project page adds: signal taxonomy · scoring logic · alert examples · false-positive rules · sources.

---

## 6. Deliverable docs (editable `.docx`)

Produced as Word files you can edit; same content seeds the matching site pages.
1. **Apollo Reach Out** — filters (above), script, Perplexity enrichment, re-import → sequence flow.
2. **PitchBook → Attio Pipeline** — purpose, investor linking, write formats, re-import.
3. **Cloud Intelligence Overview** — the marketable external/Capabilities piece.

---

## 7. Build order

1. **This plan** ← approved
2. **Two project docx files** (Apollo Reach Out + PitchBook → Attio) — *done*; the Overview/Capabilities doc comes with the site
3. **Reorganize the GitHub repo** into the §3 layout (do this *before* scaffolding so all site/CI paths are stable)
4. **Scaffold Docusaurus** (`hub/`, config, sidebar, project-page template, Dockerfile)
5. **Fill content** from the docx for the two built projects + Capabilities
6. **Deploy to Cloud Run + IAP**, map custom domain
7. **Wire CI/CD** (Cloud Build on push to `main`) + **weekly scheduled rebuild**
8. **Build Co-Invest Radar** (separate workstream; documented in the hub as it's built)

---

## 8. Open decisions & notes

- **Custom domain:** confirm subdomain (suggest `intel.id8investments.com`).
- **GCP project:** which project/billing account to deploy under?
- **External tier:** is Capabilities truly public, or IAP-gated and shared as a PDF export? (Plan assumes PDF export from gated content.)
- **Cost:** Cloud Run scales to zero — expect single-digit USD/month at this traffic, plus domain + minor egress.
- **CI/CD choice:** Cloud Build (GCP-native) vs GitHub Actions — defaulting to Cloud Build unless you prefer Actions.
