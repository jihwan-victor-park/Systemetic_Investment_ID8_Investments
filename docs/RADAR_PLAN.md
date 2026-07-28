# Radar — Full Plan

> **Status:** plan for review. Nothing built yet.
> **Goal (Oscar, 2026-07-28):** have **contact established at least 3 months
> before** a company opens its next round.
> **Mandate screen:** we co-invest, so a company only qualifies if its next round
> is likely to be **led by a Tier 1 with new money**. That is a hard screen, not a
> scoring bonus.
> **Membership:** the **Top 10 VC workflow** and the **Qualified deals workflow**
> only, at Series B or below. No other source admits a company.
> **Companion docs:** [RADAR_SIGNAL_ENGINE.md](RADAR_SIGNAL_ENGINE.md) — why each signal works. [Radar_Summary_for_Leadership.md](Radar_Summary_for_Leadership.md) — the short version.
> **Written:** 2026-07-28

---

## 0. What Radar is

ID8 co-invests at Series B and later, alongside a Tier 1 lead putting in new
money. That shapes everything below in two ways:

1. **We need to be known before the round forms.** Not twelve months of
   relationship-building — the target is **contact by three months before the
   raise opens**, which is early enough to be in the conversation and late enough
   to be relevant.
2. **A well-timed company we can't co-invest into is worthless to us.** If the
   next round won't be led by a new Tier 1, the deal fails our screen no matter
   how confidently we predicted its timing.

Radar is therefore a watch list of companies that just raised — so their next
round is in our mandate — filtered to those that can plausibly attract a new
Tier 1 lead, and monitored so we know when to make contact.

### 0.1 The three dates that matter

```
        signals appear          WE ACT              contact must exist        round opens
             │                    │                        │                      │
    ─────────┼────────────────────┼────────────────────────┼──────────────────────┼──────▶
          T−6mo                T−4.5mo                  T−3mo                   T−0
      prepare the route     make contact              ← the goal            they go to market
      (internal only)       (the action)
```

**The alert must fire earlier than the goal.** Securing an introduction takes
roughly 4–6 weeks, so to have contact by T−3 the system must flag the company at
about **T−4.5**. Alert lead time and contact lead time are not the same number,
and the gap between them is the time it takes to work a route in.

### 0.2 What the system produces

```
Northwind Systems
  Predicted raise window:      Jan – May 2027   (opens ~Feb 2027)
  Contact by:                  Nov 2026   ← 3 months before predicted open
  P(opens within 180 days):    41%   ▲ from 32% four weeks ago     ← the action trigger
  P(opens within 90 days):     22%                                 ← the urgency read
  Confidence:                  medium — 2 independent families, data 5 days old

  MANDATE SCREEN               ✓ qualifies
    Geography                  Boston, US                                  ✓
    Next round in mandate      Series C                                    ✓
    New Tier 1 lead likely     HIGH — Series B led by <Tier 1 we co-invest
                               alongside>; sector and check size squarely in
                               two other Tier 1s' active range
    Insider-round risk         LOW — no bridge, no flat round, lead's fund
                               is late in its cycle so a new lead is likely

  CAPITAL CLOCK                $32M closed 10 Feb 2026 · 81 staff · est. burn
                               $1.89M/mo · est. cash-out Aug 2027
  EVIDENCE
    • Director of Finance posted 14 Sep, still open          [preparation]
    • VP Sales posted 3 Oct — hiring turned senior           [preparation]
    • Two enterprise customers announced Sep–Oct             [narrative]

  ACCESS ROUTE                 Series B lead is a firm we co-invest alongside;
                               partner-level contact already in Attio
  ACTION                       Request intro this week. Target contact by 6 Nov.
```

---

## Part I — Intake and the mandate screen

### 1.1 The two pathways

Both already run, differing only in the saved search behind the export:

```
PitchBook saved search ──┬── Top 10 VC search        → /process-top10  (top10=True)
                         └── Qualified deals search  → /process | /process-watchlist
   │  (a person runs the export by hand)
   ▼
.xlsx dropped in a Google Drive folder  →  n8n polls Drive every minute
   ▼
POST Cloud Run  →  Attio Deal created, one per row
   ▼
Firestore companies/{slug}  (metadata only, no screen)
```

### 1.2 What each export row already gives us

No new data source is needed to build the model:

| Column | Attio slug | Used for |
|---|---|---|
| `Series` | `series` | routing rule; is the *next* round in mandate |
| `Deal Size` | `deal_size` | **capital clock** |
| `Deal Date` | `deal_date` | **capital clock** — when the clock started |
| `Post Valuation` | `post_valuation` | check-size fit; next-round size estimate |
| `Revenue` | `revenue` | burn model (net vs. gross) |
| `HQ Location` | `location` | **geography screen**; cost-per-head; which registry to watch |
| `Lead/Sole Investors` | `lead_investors_8` | **Tier 1 screen** + access route |
| `New Investors` | `new_investors_5` | Tier 1 screen + access route |
| `Investors` | `investors_5` | Tier 1 screen + access route |
| *(Top 10 VC flag)* | resolved by title | Tier 1 screen + access route |

**`Deal Date` is written to Attio today and never read back.** That is the one
blocking gap — the capital clock depends on it. Phase 0 fixes it.

### 1.3 The mandate screen, applied at intake

Because we co-invest, most companies can be ruled out before we spend a single
sensor call on them. Applied in order, all deterministic:

| # | Screen | Rule | Source |
|---|---|---|---|
| S1 | **Geography** | HQ in North America or Europe | `location` |
| S2 | **Next round in mandate** | current round ≤ Series B, so the next is B or later | `series` |
| S3 | **Tier 1 on the cap table** | at least one Tier 1 / co-invest firm among lead, new, or all investors — or the Top 10 VC flag | investor columns |
| S4 | **Not structurally insider-bound** | last round wasn't a bridge or flat round with no new money | `series`, `post_valuation` |

**S3 is the important one and it's a hard gate.** A company with no Tier 1 anywhere
on the cap table is very unlikely to attract a new Tier 1 lead at its next round,
which means we can't co-invest even if we time it perfectly. Those companies are
recorded but **never sensed and never escalated** — no budget, no partner
attention.

This screen is what makes the whole system cheap: it cuts the sensed population
to the companies that could actually become deals.

### 1.4 Predicting the lead: access and mandate are different questions

A distinction ID8's own screen already makes ("new vs. re-up"), and the system
must keep them apart because they can point opposite ways:

| | Question | Answered by |
|---|---|---|
| **Access route** | *Can we get in front of them?* | Who is on the cap table now, and who we know there |
| **Mandate fit** | *Will a NEW Tier 1 lead the next round?* | Whether the round is likely led by a new outside firm rather than done internally |

An existing Tier 1 investor is excellent for **access** and no guarantee of
**mandate fit** — if the insiders simply do the next round themselves, there is no
new-money Tier 1 lead and the deal doesn't qualify for us.

`newTier1LeadLikely` — high / medium / low, with reasoning:

| Pushes toward a new Tier 1 lead | Pushes toward an insider round |
|---|---|
| Multiple Tier 1s on the cap table (they compete for the lead, or bring one) | Single small investor holding most of the cap table |
| Round size trajectory in Tier 1 check-size range | Next round likely small relative to their last |
| Sector squarely in named Tier 1s' active areas | Sector out of favour with the relevant firms |
| Existing lead's fund late in its cycle (less dry powder for a big insider round) | Lead recently closed a large new fund and can lead again |
| Strong growth metrics — an outside firm will want it | Flat/declining metrics — insiders bridge instead |
| Press naming outside interest | Last round was a bridge or flat |

### 1.5 Two changes to the pathways

**(a) Series B and below route to Radar.** [`determine_stage`](pipeline/app.py:558)
sends Series A or earlier today; widening `_EARLY_SERIES_RE` to include
`series\s*b\d*` is a one-line change.

Consequence to accept: Series B deals stop getting an automatic Stage 1 deep
screen on arrival — they arrive cold and are screened when the model promotes
them. Deferred, not lost. Sharper alternative: route on **`Deal Date` + series**,
so a Series B that closed months ago goes to Radar while one still raising stays
in Qualified for immediate screening.

**(b) Remove the manual trigger.** Cheapest first:
1. **Staleness alarm** — alert if no export has landed in N days. Hours of work; kills the silent-failure mode. Do this regardless.
2. **Scheduled export delivery** into the same Drive folder — nothing downstream changes.
3. **PitchBook API pull** — needs a licensing answer; price it before assuming.

### 1.6 The relevance exclusion list — editable from the Radar tab

The mandate screen (§1.3) is *structural*: geography, stage, Tier 1 on the cap
table. It cannot catch "this is a biotech" or "this is a real-estate brokerage" —
that only becomes visible from the company's **description, category or vertical**,
and often only after a scan has enriched those fields.

**This already exists, hardcoded.** [`sectorRelevance.js`](hub-next/src/lib/sectorRelevance.js)
holds an `EXCLUDED_KEYWORDS` array — biotech, pharma, therapeutic, life science,
drug discovery, clinical trial, medical device, diagnostics, genomic, oncology,
agriculture, agtech, farming, real estate, proptech — matched against
`description + category + industry`. Its own comment says to *"extend
EXCLUDED_KEYWORDS as more off-thesis verticals come up in practice."* Which means
every new exclusion is a code change and a deploy. **That's the thing to fix.**

#### Rule types

Stored in Firestore, edited from the Radar tab by an internal user:

| Type | Example | Matches against |
|---|---|---|
| **Keyword / phrase** | `biotech`, `drug discovery`, `staffing agency` | description, category, industry, vertical |
| **Category / vertical** | category = `Pharmaceuticals and Biotechnology` | the structured field only — precise, no false matches |
| **Named company** | *this specific company, regardless of rules* | company identity |
| *(optional, default off)* **Required keyword** | must mention AI/ML | description |

Each rule carries a label, who added it, when, and a note — so in six months it's
clear why `proptech` is on the list.

**A note on the required-keyword type: it's far more dangerous than the exclusions
and should stay off by default.** An exclusion drops companies that say something
disqualifying; a requirement drops every company whose description is merely thin or
generic, which is a large share of them. The existing AI-relevance pass in
[`portfolio_prefilter.py`](deal_intelligence/portfolio_prefilter.py) already handles
this the right way — high recall, "when in doubt, pass it through."

#### Matching: word boundaries, not substrings

The current code uses `text.includes(kw)`, which is fine for a curated list written
by whoever wrote the code, and a trap for a list typed freely into a text box:
`crypto` matches **crypto**graphy, so a confidential-compute company gets silently
dropped. `ag` matches nearly everything.

So: **word-boundary matching**, explicit multi-word phrase support, and a minimum
keyword length with a warning below it. Cheap to implement, and it's the difference
between a tool that's safe to hand someone and one that quietly loses companies.

#### Three places rules apply

1. **At intake**, before the first scan — cheapest, and stops us paying to watch
   something we'd never invest in.
2. **On every scan** — because descriptions get enriched after intake and companies
   pivot. A company that looked like generic "data infrastructure" in August can
   read clearly as clinical-trial software by November, and the scan is where that
   surfaces.
3. **Retroactively, the moment a rule is saved** — this is the dynamic part. Adding
   `proptech` immediately re-evaluates every company on Radar and drops the matches.
   No deploy, no backfill script.

#### Nothing is ever deleted

An excluded company gets `state: 'excluded'` plus `excludedBy` (which rule fired),
`excludedAt`, and the matched text. It stops being scanned — that's the point, and
it's a direct budget saving — but it stays visible in a collapsed **"Excluded (N)"**
section on the Radar tab, with one-click restore.

Silent disappearance is the failure mode to avoid. A rule that over-fires must be
discoverable and reversible, and it will over-fire eventually.

#### Precedence

```
manual keep  >  manual exclude  >  rule exclude  >  in scope
```

**"Keep anyway"** pins a company against all current *and future* rules — the escape
hatch for the good company whose description happens to contain a bad word. Without
it, someone re-adds a keyword three months later and quietly loses the company again.

#### Preview before saving — the important UX detail

When a keyword is typed, show **how many companies on Radar it would drop, and which
ones, before saving.** Typing `medical` and seeing *"would exclude 7 companies,
including <a company you like>"* is what stops a careless rule from silently killing
a chunk of the list. Same preview when a rule is removed: how many come back.

#### Suggested rules — the dynamic bit

When several companies are manually excluded, look for terms common to their
descriptions and absent from the kept ones, and propose them: *"4 of your last 6
manual exclusions mention `clinical` — add it as a rule?"* Plain word-frequency
comparison, no AI, no cost. The list curates itself from your own decisions instead
of waiting for you to notice a pattern.

#### Keeping it separate from the fit score

The hub already treats "off-thesis / wrong geography" and "weak fit score" as two
independently toggleable reasons rather than one combined switch, because they answer
different questions — *is this even our market* vs. *is this a strong company in our
market*. Radar keeps that convention: exclusion rules, mandate screen, and low
probability are three distinct states with three distinct reasons, never merged into
one "hidden" flag.

### 1.7 What we accept

| | Consequence |
|---|---|
| Coverage | Radar is what the two saved searches return, minus the mandate screen. Those search definitions define the entire universe and deserve periodic review |
| Discovery latency | We stay PitchBook-bound for *finding* companies. Filings make us fast at noticing a *tracked* company raised, never at finding a new one |
| Volume | After the S1–S4 screen, likely 100–300 companies. Every sensor runs on everyone at full cadence — no tiering needed |

---

## Part II — Sources: exactly what we read

### 2.1 Regulatory filings — *did they raise?*

| Source | Endpoint | Access | Gives us | Cadence |
|---|---|---|---|---|
| **SEC EDGAR** (US) | `efts.sec.gov` full-text search; `sec.gov/cgi-bin/browse-edgar` | **Free, no key.** Descriptive User-Agent required; ~10 req/s | **Form D** — issuer, date, total offering, amount sold, revenue bracket, and *related persons* (execs and directors, **which often names the new investor board member — i.e. who led**). Filed within **15 days of first sale** | daily |
| **Companies House** (UK) | `api.company-information.service.gov.uk` | **Free, registered key** | **SH01** share allotments (within one month), officer appointments and terminations, filing history | daily |

Fastest public confirmation that exists — **weeks ahead of PitchBook**. Three jobs:
reset the capital clock, tell us whether we had contact in time, and grade every
prediction (Part VIII). The related-persons list also tells us **who actually led**,
which is how we score whether our `newTier1LeadLikely` calls are any good.

Honest limits: the US pre-close filing that would predict a raise (amended
certificate of incorporation authorising new preferred stock) sits in Delaware
behind paid per-document retrieval with no bulk API — real signal, not
economically accessible. Outside the US and UK, registries are patchy.

### 2.2 Hiring — *are they preparing?* (highest-value family)

A company **preparing to raise** hires narrow and senior — a finance leader, a
data hire, a sales executive. A company that just **closed** hires broad and
junior. Both read as "hiring is up" to a naive counter and they mean opposite
things.

| Source | Endpoint | Access | Gives us |
|---|---|---|---|
| **Greenhouse job boards** | `boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` | **Free, public JSON, no key** | Complete live role list: title, department, location, first-seen date |
| **Lever** | `api.lever.co/v0/postings/{company}?mode=json` | **Free, public JSON** | same |
| **Ashby** | `api.ashbyhq.com/posting-api/job-board/{token}` | **Free, public JSON** | same |
| **Workable / other ATS** | provider public job endpoints | free | same |
| **Company careers page** | their own site | free fetch | fallback where no ATS is detected |
| **Apollo** | organisation enrichment + job postings | **already licensed** | employee-count estimate; postings where no public board exists |

**Why this beats scraping LinkedIn:** most venture-backed companies host jobs on
Greenhouse, Lever or Ashby, and all three publish a **public JSON API intended for
consumption** — complete, structured, timestamped, free, no terms-of-service grey
area. We read the company's own job board.

One-time setup per company: detect the ATS from the careers-page link or embedded
board token; store `atsProvider` + `atsToken`. After that, one free HTTP call per
company per week.

### 2.3 Narrative and press — *are they warming the market?*

| Source | Access | Gives us |
|---|---|---|
| **Google News RSS** per company | free | funding rumours, launches, customer wins, layoffs, **and reports naming interested investors** |
| **Perplexity** monthly targeted pass | already licensed | synthesis where RSS is thin; investor-interest reads |
| **Company website** — `/pricing`, `/customers`, `/press`, `/security`, `/about` | free fetch | enterprise tier added, trust/SOC-2 page appearing, logo wall growing |
| **Hacker News** (`hn.algolia.com/api/v1/search`) | free API | developer-community mention volume |
| X / Reddit | X API paid; Reddit needs auth | founder cadence, metrics claims — **deferred to Phase 9** |

Weakest family, and weakest where our mandate is strongest — B2B infrastructure
emits little useful social signal. Never allowed to carry a promotion alone.

### 2.4 Tier 1 activity — *who is leading rounds right now*

New, and specific to a co-invest fund. To judge `newTier1LeadLikely` we need to
know what the Tier 1s are actually doing:

| Source | Gives us |
|---|---|
| Form D related persons across all filings | which firms are taking board seats, i.e. leading |
| Press funding announcements | who led, at what stage, in what sector |
| Fund-close announcements | which firms just raised and have fresh dry powder |

Maintained as a small rolling profile per Tier 1 firm — recent lead activity by
stage and sector, and fund-cycle position. Cheap, and it's what turns "they have a
Tier 1 investor" into "a new Tier 1 is plausibly going to lead this round."

### 2.5 What we already hold

Apollo contacts and Attio relationships for the route; the deal's investor
columns; ID8 portfolio burn data for calibrating cost-per-head.

### 2.6 Candidate sources — flagged, not yet evaluated

Two came up in intake brainstorming (2026-07-28) as possible additions. Neither
is committed to: both are new paid vendors, and Part IX's whole cost case rests
on the free-first design in §2.1–§2.5, so either needs a real cost/access check
before it earns a place in the build.

| Source | What it could add | Where it would slot in | Open question |
|---|---|---|---|
| **[Sacra](https://sacra.com/)** | Deep private-company research: revenue and growth estimates, business-model analysis, sourced and cited | **Fundamentals/revenue triangulation for the capital clock** (§3) — today's burn model leans on headcount alone; a real revenue estimate would let net-burn replace gross-burn wherever it's available, and would sharpen the "warming the market" narrative signal (§2.3) with sourced growth claims instead of press-only inference | Cost per seat/API call; coverage depth on companies at ID8's actual stage (Series B-adjacent), not just the well-known names research tools tend to cover well |
| **Crunchbase** | Funding-event tracking — a broader, paid alternative/supplement to the free SEC Form D / Companies House filings sensor (§2.1) | **Confirmation clock discovery** — Crunchbase tracks non-US/UK rounds the free filings feeds structurally can't reach, and often earlier than a press cycle | Whether its bulk/API access is priced sanely for continuous monitoring at Radar's scale, and whether its lead-time over Form D (which already lands in ~15 days) is actually worth paying for |

Neither changes anything in Parts III–X as written — if evaluated and adopted
later, Sacra folds into the capital clock's inputs (§3, Part III) and Crunchbase
into Clock 1 (§2.1, Part V) without restructuring either.

---

## Part III — Metrics

Every metric is a **time series** — the prediction reads changes, not snapshots.
One sample of a job board is nearly worthless; twelve monthly samples showing
52 → 84 staff with a Director of Finance role appearing in month seven is the
whole signal.

### Capital clock

| Metric | Definition | Source |
|---|---|---|
| `roundSize`, `roundDate` | last round raised and its close date | intake |
| `monthsSinceRound` | today − roundDate | computed |
| `headcount` | employee estimate | Apollo, monthly |
| `costPerHead` | fully-loaded annual cost by class and geography | table below |
| `estMonthlyBurn` | headcount × costPerHead ÷ 12 | computed |
| `estCashOutDate` | when capital runs out at projected burn | computed |
| `runwayMonths` | estCashOutDate − today | computed |
| `predictedWindowOpen` | cashOut − 12mo, **then shifted out of any dead zone** (§6.3) | computed |
| **`contactByDate`** | **predictedWindowOpen − 3mo**, then pulled *earlier* if it lands in a dead zone | computed |
| **`alertAtDate`** | **contactByDate − 6wk** — when the system must flag it | computed |
| `capitalIntensity` | high / medium / low — drives both burn and scan interval | classified from sector |
| **`nextScanAt`** | the computed next scan date (§6.2) | computed |
| `nextScanReason` | one line explaining the interval, so the schedule is auditable | computed |
| `scanCount`, `lastScanAt` | scan history | computed |

| Class | $/head/yr |
|---|---|
| US software, growth stage | 220–260k |
| European software | 130–180k |
| AI-heavy (own model training) | 300–400k+ — **compute often exceeds payroll; burn under-modelled** |
| Hardware / deeptech / defence | 250k+ **plus capex** — runway maths weakest |
| Consumer with paid acquisition | payroll + marketing spend |

### Mandate screen

| Metric | Definition |
|---|---|
| `geoPass` | HQ in NA or Europe |
| `nextRoundInMandate` | next round is Series B or later |
| `tier1OnCapTable` | boolean, plus `tier1Firms[]` matched from the investor columns |
| `top10VCFlag` | from the Attio deal |
| `newTier1LeadLikely` | high / medium / low, with reasoning (§1.4) |
| `insiderRoundRisk` | high / medium / low — the counter-case |
| `mandatePass` | S1 ∧ S2 ∧ S3 ∧ S4 — gates all sensing and escalation |
| `relevancePass` | no exclusion rule matched (§1.6) — a **separate** gate from `mandatePass`, with its own reason |
| `excludedBy` | which rule fired: keyword / category / manual, plus the matched text |
| `keepAnyway` | manual pin that overrides all current and future rules |

### Hiring composition — the discriminator

| Metric | Definition |
|---|---|
| `openRoles` | total live postings |
| `rolesSeniorFinance` | CFO, VP Finance, Director of Finance, Controller, Head of FP&A |
| `rolesExecGTM` | CRO, VP Sales, VP Marketing, Head of Revenue |
| `rolesCorpDev` | Head/Director of Corporate Development, Strategic Finance |
| `rolesRecruiting`, `rolesDataAnalytics` | recruiters/TA; data engineering, analytics, BI |
| `seniorityRatio` | Director+ postings ÷ total postings |
| `juniorICShare` | IC postings ÷ total postings |
| `roleFirstSeen[role]` | when each posting appeared — **required**, weight depends on signal age |
| `roleFilledAt[role]` | when a posting disappeared — a *filled* senior finance role beats an open one |

### Growth and health

| Metric | Definition |
|---|---|
| `headcountGrowth90d`, `headcountGrowthAnnualized` | derivative of the series |
| `headcountInflection` | second-derivative sign change |
| `execJoins`, `execDepartures` | VP+ changes (Companies House officers in the UK; Apollo/press elsewhere) |
| `financeLeaderDeparted`, `layoffFlag` | strong negatives |

### Narrative

| Metric | Definition |
|---|---|
| `pressMentions30d` | rolling count |
| `fundingRumorFlag` | "in talks to raise" language detected |
| `investorInterestNamed` | press naming a specific interested firm — feeds `newTier1LeadLikely` |
| `customerAnnouncements90d`, `productLaunch90d` | narrative signals |
| `siteChanges` | enterprise tier added, trust page added, logo wall grew, press page created |

### Output

| Metric | Definition |
|---|---|
| **`p180`** | probability of opening a raise within 180 days — **the action trigger** |
| `p90` | probability within 90 days — the urgency read |
| `predictedWindowStart` / `End` | date range |
| `confidence` | independent families active, data freshness, sensor coverage |
| `familiesActive` | how many of the four predictive families contribute |
| `distressFlag` | the "dying, not raising" branch |
| `accessScore` 0–10 | from the investor columns and our contacts |
| **`contactStatus`** | `none` / `requested` / `made` — plus `contactMadeAt` |
| **`contactLeadDays`** | contactMadeAt → actual round date. **The KPI** (Part IX) |

---

## Part IV — The model

Two layers, **neither using a language model** — the number must be reproducible
and auditable. AI only *explains* a number computed in arithmetic, and only for
companies that have already crossed a threshold and passed the mandate screen.

### 4.1 Baseline: the capital clock

Companies raise when cash gets short. They start a process with 9–12 months of
runway and aim to close with 6. So the baseline hazard is low until
`predictedWindowOpen` (cash-out − 12mo), peaks around cash-out − 8mo, and stays
elevated after. This replaces "months since last round vs. typical cadence," a
crude proxy for something we can compute directly.

### 4.2 Two horizons, one for acting and one for urgency

Because the goal is contact by T−3 and an introduction takes 4–6 weeks:

- **`p180` is the action trigger.** A raise plausibly within six months is exactly
  when we must start working a route in, to have contact by T−3.
- **`p90` is the urgency read.** If p90 is high and `contactStatus` is still
  `none`, we are behind — that gets flagged as a likely miss, not celebrated as a
  hot lead.

Promoting on p90 alone would systematically deliver contact *after* the deadline.
That was the flaw in the previous version of this plan.

### 4.3 Signals as multipliers with peak-effect delays

Each signal multiplies the baseline, weighted by **how old it is** — not a simple
decay. A finance-leader hire is *more* predictive four months on than the week it
appears, because the hire exists to run a process that starts later. A press
rumour is maximal immediately and worthless in nine months.

| Signal | Peak effect | At peak | Family |
|---|---|---|---|
| Senior finance role posted / filled | T+4mo | ×2.5 | preparation |
| Corp-dev role posted | T+2mo | ×2.2 | process |
| Press: "in talks to raise" | immediate | ×6.0 | process |
| Independent board member added | T+2mo | ×1.8 | process |
| Runway < 9 months | flat | ×2.2 | clock |
| Headcount growth > 40% annualised | concurrent | ×1.6 | preparation |
| Exec GTM hiring burst | T+3mo | ×1.4 | preparation |
| Recruiter hiring | T+3mo | ×1.3 | preparation |
| Product GA / major launch | T+2mo | ×1.4 | narrative |
| Marquee customer or partnership | T+2mo | ×1.3 | narrative |
| Enterprise tier / trust page added | T+4mo | ×1.2 | narrative |
| Last round was a bridge | flat | ×1.5 | clock |
| **Layoffs in last 90 days** | immediate | **×0.6** | negative |
| **Finance leader departed** | immediate | **×0.5** | negative |
| **Headcount declining > 10%** | concurrent | **×0.4** | negative |

**Every number is a hand-set prior**, encoding the mechanism reasoning in
[RADAR_SIGNAL_ENGINE.md](RADAR_SIGNAL_ENGINE.md) §2. They are wrong in detail and
get replaced by calibrated values (Part VIII). Stating them explicitly is what
makes them correctable.

Note the lead-time consequence: the signals that matter most for a T−4.5 alert are
the **preparation** family, because they're the only ones with 6–9 months of lead.
Process signals arrive too late to help us hit T−3 — when a press rumour lands,
we should already have contact.

### 4.4 Guardrails

1. **Mandate gate first.** `mandatePass = false` → no sensing, no escalation, ever.
2. **Two-family rule.** Promotion requires signals from **≥2 of the four
   predictive families**. Four job postings are one signal wearing four hats. Sole
   exception: a credible press rumour may promote alone.
3. **Composite cap** at ×8 total.
4. **Hysteresis.** Promote at p180 ≥ 35%, demote only below 25%, minimum 30 days
   in a state — otherwise the list flickers and nobody trusts it.

### 4.5 The distress branch

A company past its window is **equally likely to be raising on strength or quietly
failing.** An explicit branch, not a weighting:

| Past window, and… | Reading |
|---|---|
| headcount growing, senior/finance hiring | **imminent raise** |
| headcount flat, nothing posted | **zombie** — minimum sensing, never escalate |
| headcount falling, finance leader gone, layoffs | **distress** — suppress, flag, never present as an opportunity |

Escalating a dying company to a partner is worse than having no model.

---

## Part V — Triggers: the concrete logic

Three clocks. Cheap sensing is **scheduled**; expensive AI research is
**event-driven only**.

### Clock 0 — at intake, once

| Trigger | Condition | Fires |
|---|---|---|
| **T0 Mandate screen** | S1–S4 (§1.3) | Pass → continue to T0b. Fail → record with reason, **no sensing** |
| **T0b Relevance rules** | exclusion rules (§1.6) match description / category / vertical / company name | Match → `state='excluded'` with the rule that fired, **no sensing**. No match → begin sensing, compute `contactByDate`, `alertAtDate`, `nextScanAt` |

### Clock 1 — daily, free

| Trigger | Condition | Fires |
|---|---|---|
| **T1 Round confirmed** | Form D or SH01 appears for a tracked company | Reset the clock · **record `contactLeadDays`** — did we hit T−3? · **read the related-persons list to see who led**, scoring our `newTier1LeadLikely` call · if the new round is in mandate and we had no contact, log a **miss with a reason** |
| **T2 Officer change (UK)** | Companies House appointment/termination at VP+ | Preparation or negative signal by role |

### Clock 2 — sensors on a rhythm

| Trigger | Condition | Fires |
|---|---|---|
| **T3 Senior finance role appears** | posting matches finance-leader titles | Preparation signal, dated from first-seen · recompute p180 |
| **T4 Senior finance role filled** | posting disappears, matching title appears in Apollo | Upgrade the signal — the apparatus now exists |
| **T5 Composition shift** | `seniorityRatio` rises while `openRoles` is flat or falling | Preparation signal — the pre-raise pattern |
| **T6 Corp-dev role appears** | matches corp-dev titles | **Process** signal — and if `contactStatus` is `none`, flag that we're late |
| **T7 Headcount growth** | > 40% annualised over two consecutive samples | Preparation signal |
| **T8 Headcount decline** | > 10% over 90 days | **Distress flag** — suppress escalation |
| **T9 Runway threshold** | `runwayMonths` < 12 | Baseline hazard jump; recompute `contactByDate` |
| **T10 Funding rumour** | "in talks to raise" in press | **Immediate escalation**, bypasses the two-family rule. If `contactStatus` is `none`, this is a **near-miss** — act today |
| **T11 Narrative burst** | customer/partnership/launch, or enterprise-tier / trust-page change | Narrative signal |
| **T12 Layoffs or finance-leader departure** | news sweep or exec-change detection | **Distress flag** |
| **T13 Investor interest named** | press names a firm circling | Raises `newTier1LeadLikely`; strong access signal |

### Clock 3 — action triggers *(the ones that produce work for a human)*

| Trigger | Condition | Fires |
|---|---|---|
| **T14 Route preparation** | p180 ≥ 20%, or any preparation signal fires | **Internal only, no contact.** Identify the specific route: which Tier 1 on the cap table, who we know there, is the contact in Attio. Fix gaps now, while there's time |
| **T15 Contact window opens** | **p180 ≥ 35% and mandatePass** | **The main event.** Research pass → the card → assess `newTier1LeadLikely` → named route → **request the intro**, target contact within 6 weeks |
| **T16 Deadline approaching** | `contactByDate` within 30 days and `contactStatus` ≠ `made` | Escalate to a person by name. This is the last chance to hit the goal |
| **T17 Behind schedule** | p90 ≥ 40% and `contactStatus` = `none` | Flag as a likely miss — act immediately and log why we were late |
| **T18 Research rate limit** | — | Max one research pass per company per 30 days |

### Data-health triggers (not signals)

| Trigger | Condition | Fires |
|---|---|---|
| **T19 Sensor failure** | a fetch fails | Record `unknown` — **never** `no change`. A 403 must not read as "headcount flat" |
| **T20 Sensor stale** | no successful sample in 45 days | Data-health alert; lower confidence on the card |
| **T21 Export stale** | no PitchBook export in N days | Alert — intake has silently stopped |

### Relevance triggers

| Trigger | Condition | Fires |
|---|---|---|
| **T22 Rule saved or removed** | an internal user edits the exclusion list | **Re-evaluate every Radar company immediately.** Newly matching companies → `excluded`, stop scanning. Newly unmatched → restored to monitoring with `nextScanAt` recomputed. Report the count changed |
| **T23 Scan reveals off-thesis** | a scan's enriched description / category now matches a rule | `state='excluded'`, stop scanning, record the matched text — the description that looked generic at intake now reads clearly off-thesis |
| **T24 Suggested rule** | ≥3 recent manual exclusions share a term absent from kept companies | Propose it as a rule. Word-frequency comparison, no AI |

---

## Part VI — Scan scheduling

**Volume (Oscar, 2026-07-28): ~9 companies today, ~100 within a few months**, added
weekly. That size settles the architecture: small enough that every company gets
the full treatment, large enough that scan timing has to be decided per company
rather than by one global rhythm.

### 6.1 Two layers: a free ledger and a scan

| | The ledger | The scan |
|---|---|---|
| **What** | Snapshot the cheap public sources and append to the time series. No analysis, no output | Read the accumulated ledger, recompute the model, produce a status, **and decide when to scan next** |
| **Cadence** | Fixed and frequent — job boards weekly, headcount monthly, filings daily | Per-company, adaptive (§6.2) |
| **Cost** | ~$0 (public JSON, free APIs) | free arithmetic; paid AI only when a threshold is crossed |
| **Produces** | history | a decision |

**Why the ledger stays frequent even though scans are not.** A senior finance role
typically stays open 4–10 weeks. If we only looked at the job board when we scanned,
a two-month scan gap would miss the single most valuable signal in the entire system
— posted and filled between visits, invisible forever. The job-board pull is one
free HTTP call, so there is no reason to ration it: **sample weekly, reason
occasionally.** The ledger is what makes an infrequent scan able to see history it
didn't personally witness.

### 6.2 The scan schedule

**Target (Oscar, 2026-07-28): about 5 scans per company per year** for a company
in its first year on Radar — not a hard cap, a realistic base rate. It reconciles
cleanly with the design below: **3 adaptive scans** for a company that hasn't
shown any urgent signal yet, **plus the 2 fixed calendar sweeps** every company
gets regardless of its own schedule (§6.3) = **5**. A company that enters its
critical run-up naturally scans more often than that — which is correct, that's
where the budget should concentrate — while the common case (a company sitting
quietly, months from its window) coasts near this 5/year floor for as long as it
stays quiet.

**Fixed opening sequence, from the round's close date:**

| Scan | When | Why |
|---|---|---|
| **Scan 1** | **T+4 months** | The first 3 months post-close are deployment noise — broad junior hiring, new office, brand refresh. Nothing diagnostic. Month 4 is the earliest a genuine signal can appear |
| **Scan 2** | **T+6 months** | Establishes a *direction*. One reading is a level; two are a trend, and the trend is what the model actually consumes |

**After that, the interval is computed.** Base interval from time remaining until
the estimated raise window opens:

| Months until predicted window opens | Scan every |
|---|---|
| > 12 | 4 months |
| 8–12 | 3 months |
| 5–8 | 8 weeks |
| **3–5** | **6 weeks** — the critical zone; we must act at T−4.5 |
| < 3 | 4 weeks — late, or already in contact |

Then modified, multiplicatively:

| Factor | Effect on interval | Reasoning |
|---|---|---|
| **Capital intensity — high** (hardware, deeptech, defence, own-model AI training) | **×0.7** | Burn faster, raise sooner and more often; compute and capex mean our payroll-based burn estimate is too low, so scan more to catch reality |
| **Capital intensity — low** (efficient SaaS, near-breakeven, revenue-funded) | **×1.4** | Can go 30+ months. Scanning them often is wasted effort |
| **Round size large relative to burn** (runway > 24mo) | ×1.3 | Nothing will happen for a while |
| **Round size small / bridge / extension** | ×0.7 | Short clock, and bridges are followed by real rounds sooner |
| **Momentum strong** (headcount accelerating, narrative signals firing) | ×0.8 | Things are moving; look more often |
| **Quiet** (no signal across 2 consecutive scans) | ×1.3 | Back off, don't abandon |
| **Distress flagged** | ×1.5 | Watch, but this is not an opportunity — spend attention elsewhere |
| **Any preparation signal active** | **floor of 6 weeks** | Keep routine re-checks reasonably tight once a finance role has appeared — the actual guarantee against missing something sharper comes from the ledger (below), not this floor alone |

Bounds: minimum 4 weeks, maximum 4 months. `nextScanAt` and the reason for it are
stored on the company, so the schedule is always explicable.

**Why the floor can relax from the tighter version of this plan.** The routine
schedule above is the *fallback* — what happens if nothing interesting occurs. It
is not the only thing standing between us and missing a signal: the free weekly
job-board pull (§6.1) already triggers an out-of-cycle scan the moment something
concrete appears (a finance role posted, a corp-dev hire, a filing), independent of
whatever `nextScanAt` currently says. That pull-forward mechanism is what protects
the T−4.5 alert deadline; the routine floor only needs to keep a baseline rhythm
during genuinely quiet stretches, which is why it can sit at 6 weeks instead of 4
without weakening the guarantee.

### 6.3 Seasonality — the dead zones

Funding processes do not launch uniformly through the year, and ignoring this is how
a model produces a confident prediction for a month in which nothing ever happens.

**Dead zones — processes do not launch here:**

| | Period | Why |
|---|---|---|
| **August** | roughly 25 Jul – 31 Aug | Partners on holiday, especially in Europe. Partner meetings thin out, IC decisions stall. Nobody launches |
| **Year-end** | roughly 15 Dec – 6 Jan | Holidays, year-end close. Dead |
| *(minor)* | US Thanksgiving week | Short, US-only |

**Launch windows — where processes actually start:**

| Window | Launch | Typical close |
|---|---|---|
| **Winter–spring** | mid-Jan → early Jun | Mar – Jun |
| **Autumn** | early Sep → mid-Nov | Oct – Dec |

*(These are well-established practitioner patterns, not something measured from our
own data. The calibration loop should replace them with ID8's observed distribution
once we have 18+ months of outcomes.)*

**Three concrete rules, and note the asymmetry — it matters:**

**(a) Push the predicted launch date *later* out of a dead zone.** If the capital
clock says the window opens 12 August, they will in practice launch in the first
week of September. If it says 22 December, they launch mid-January. The company
waits for the market to come back.

**(b) Pull *our* contact deadline *earlier* to avoid a dead zone.** If
`contactByDate` lands in late August or between Christmas and New Year, move it to
**before** the dead zone, never after — mid-July or early December. We cannot
afford to be chasing an introduction when nobody is answering email. Their dates
slip later; ours slip earlier. Never the other way round.

**(c) One exception that reverses (a): dead-zone cash pressure pulls the process
*earlier*, not later.** A company whose money actually runs out in September cannot
wait for September to start raising — it must run the process in **May–June** or
take a bridge. So when `estCashOutDate` falls in or just after a dead zone, the
predicted launch moves **earlier**, and the contact deadline with it. This is the
case most likely to catch us out, because the naive reading says "quiet summer,
relax."

**Scan-timing consequences:**

- **Never schedule a scan into a dead zone** — job boards are stale and nothing has
  moved. Push an August scan to the first week of September; push a late-December
  scan to the second week of January.
- **Two mandatory all-company sweeps a year: ~5 September and ~12 January.** These
  are the highest-information dates on the calendar — companies that decided to
  raise over the break start posting finance roles and warming up right then. A
  scan on 5 September is worth several scans in August.

### 6.4 What a routine scan costs, and what it's spent on

**`nextScanAt` itself is free** — arithmetic over the table in §6.2 plus the
seasonal calendar in §6.3. Instant, reproducible, and every scan can explain its
own next date in one line: *"6 weeks — window opens ~Feb 2027, high capital
intensity, finance role active, shifted off 27 Dec to 12 Jan."*

**Each routine scan does spend a small, capped amount of AI** — a hard ceiling of
**$0.15 per scan** (Oscar, 2026-07-28). What it buys, on a cheap-tier model (same
class as the existing `SCORE_MODEL` classification calls elsewhere in this
codebase, not a research call):

1. **Classifying the ledger's new raw text** — job titles into
   seniority/function buckets, a news snippet into rumour/distress/neutral —
   which is more reliable than pure keyword matching for the messy real-world
   phrasing job boards and press actually use.
2. **A short human-readable status line** for the company's card — the "why now"
   evidence list, not a full research report.

Both are bounded, structured tasks over a small, capped amount of new text since
the last scan (never the whole history) — that's what keeps a single scan under
the $0.15 ceiling even for a company with a busy ledger. If an unusually large
batch of new postings or news would blow past the cap, the scan falls back to
pure deterministic classification for the overflow rather than exceeding it — a
stated, visible degradation, not a silent one.

**The escalation research pass stays separate and is not this** — but it is
**capped too** (Oscar, 2026-07-28): **no more than $0.40**, not the open-ended
~$2 originally proposed. It only fires on crossing the action threshold (T15) or a
hard event (T14/T18/T22), never on every scan, and the cap is hit the same way
Stage 0 Portfolio Fit already keeps its own research pass cheap: a single call on
Perplexity's inexpensive `sonar` tier with a bounded (low/medium) search context —
not `sonar-deep-research`, which is what Stage 1's real deal screens use and is
the expensive tier. One call does the adversarial contradiction check, the
`newTier1LeadLikely` read, and route naming together; no separate Claude synthesis
step. **Every AI cost in this system, routine or escalated, now sits under 40
cents.**

### 6.5 What this costs at 100 companies

| | Volume | Cost |
|---|---|---|
| Job-board pulls | 100/week ≈ 5,200/yr | **$0** — public JSON |
| Headcount | 100/month = 1,200/yr | within the Apollo plan |
| Filing checks | 100/day | **$0** |
| Routine scans | ~5/company/yr ≈ **500/yr**, ≤$0.15 each | **≤$75/yr** |
| AI research passes | only on threshold crossings, ~60–90/yr, ≤$0.40 each | ~$25–35 |

Roughly **5 scans per company per year** on average, per the reconciliation in
§6.2: 3 adaptive + 2 fixed calendar sweeps as the floor for a quiet company,
concentrating toward the tighter end of the interval table as a company
approaches its window — which is exactly where the extra scans, and the extra
budget, should go.

### 6.6 Starting from 9 companies

- **Backfill on day one.** Any company already more than 4 months past its round
  gets Scan 1 immediately, and one a month past that gets Scan 2 as well. With 9
  companies that's a few minutes of compute.
- **The ledger has no history yet**, so the first two scans on every company are
  levels without a trend. Predictions will be low-confidence and windows wide for
  the first couple of months. That's correct behaviour, not a defect — and it's the
  strongest argument for starting the weekly job-board sampling immediately, before
  the model is finished.
- **Calibration is slower at this size than I previously stated.** 100 companies on
  18–24-month cycles means roughly **50–65 observed rounds a year**, so meaningful
  weight-fitting takes **18–24 months**, not 12. Until then the priors in §4.3
  stand, with the calibration loop reporting hit rates rather than re-fitting.

---

## Part VII — Worked example

### 7.1 A company we reach in time

**Northwind Systems** — AI data infrastructure, Boston. Arrives **August 2026** via
the Top 10 VC workflow: Series B, **$32M closed 10 Feb 2026**, led by a firm ID8
co-invests alongside.

**Mandate screen at intake (T0):** Boston ✓ · next round is Series C ✓ · Tier 1 on
the cap table ✓ (the Series B lead) · no bridge, no flat round ✓ → **passes, begin
sensing.**

**Capital clock:** 52 staff at close, 71 now, AI-heavy US class at $280k/head →
burn ≈ $1.66M/mo, ~$8.6M consumed, **~$23.4M left**. Cash-out ≈ **Aug 2027**, so
`predictedWindowOpen` ≈ **Aug 2026**… and as the burn rises with headcount through
the autumn the estimate tightens to a window opening around **Feb 2027**.

**Therefore: `contactByDate` = Nov 2026, `alertAtDate` = mid-Oct 2026.** Neither the
predicted window (Feb 2027) nor the contact deadline (Nov 2026) falls in a dead
zone, so no seasonal shift applies. Had the window landed on 22 December it would
move to mid-January, and the contact deadline with it to mid-October.

It arrives at T+6 months, already past the T+4 opening scan, so the backfill rule
(§6.6) fires Scan 1 immediately.

| | Date | What the ledger and scan show | p180 | Cost | Next scan, and why |
|---|---|---|---|---|---|
| **Scan 1** | 5 Aug | 71 staff · 9 roles, all IC eng/sales — post-round spending. No history yet, so low confidence | 18% | $0.09 | **6 wks** — window ~6mo out (base 8 wks) × 0.7 high capital intensity |
| **Scan 2** | 16 Sep | 76 staff, nothing senior. Two readings now, so a trend exists. *Falls right on the mandatory September sweep* | 22% | $0.09 | **6 wks** |
| *ledger* | 16 Sep | Same-day weekly job-board pull catches **Director of Finance, first seen 14 Sep** → **T3** | — | $0 | **pulls the next scan forward** |
| **Scan 3** | 18 Sep | Preparation signal active → **T14: prepare the route, internally.** No contact yet | 32% | $0.11 | **6 wks** — floor applies once a finance role is live |
| *ledger* | 7 Oct | **VP Sales posted 3 Oct** (senior share rising, total flat → T5) · two enterprise customers announced (T11) → two families | — | $0 | **pulls the next scan forward** |
| **Scan 4** | 8 Oct | **T15 fires.** Research pass → card → `newTier1LeadLikely` HIGH → named route → **intro requested** | **41%** | $0.12 + **≤$0.40 research pass** | **4 wks** — critical zone, window <3mo |
| **Scan 5** | 5 Nov | Finance role **filled** (T4) · enterprise pricing tier added | 52% | $0.10 | 6 wks — already known, no scramble |
| — | **6 Nov** | **Contact made.** Three months before the round opens | — | — | — |
| **Scan 6** | 17 Dec | 88 staff · **Head of Corp Dev posted** (T6) · runway 7.8mo | 61% | $0.13 | 6 wks |
| *filing* | 6 Feb 2027 | **Form D, $65M.** Related persons name a new director from a **Tier 1 not previously on the cap table** | — | $0 | clock resets, prediction graded |

**Six routine scans across six months, totalling ~$0.64, plus one research pass
capped at $0.40 — under $1.05 all in** — this company runs denser than the
~5-scan/year population average (§6.2)
precisely because it spent that whole stretch approaching its window, which is
where the schedule is designed to concentrate. A company two years out from its
next round would log two or three scans in the same period, near the population
floor, each still under the $0.15 cap. That difference — busy companies earning
more attention automatically, quiet ones costing almost nothing — is the entire
point of computing the interval instead of fixing it.

Note the mechanic that made the timing work: **hard signals in the ledger pull the
next scan forward rather than waiting for it.** The Director of Finance posting was
caught by a free weekly job-board pull on 16 September, the same day as the
scheduled scan in this run — in a less fortunate timing, the pull-forward
mechanism is what would have moved the next scan earlier regardless of what
`nextScanAt` said, and that's what let the action trigger fire on
8 October instead of late October, which is the difference between contact at T−3
and contact at T−6 weeks.

**What happened operationally.**

- **September (T14).** The first preparation signal fired. No contact yet — the
  system just told us to *get the route ready*: the Series B lead is a firm we
  co-invest alongside, and we confirmed a partner-level contact already sits in
  Attio. Internal work, two minutes.
- **8 October (T15).** p180 crossed 35% with two independent families behind it.
  One research pass, capped at $0.40, produced the card, checked it sceptically
  (was the finance hire a backfill? was the headcount jump an acquisition?), and
  assessed `newTier1LeadLikely` as **high**: multiple Tier 1s active in the sector,
  check size in range, existing lead late in its fund cycle and unlikely to lead
  alone. Intro requested the same week.
- **6 November.** Contact made. **The round opened in early February — so contact
  landed three months ahead of it. Goal met.**
- **February 2027.** The Form D confirmed both calls: the round happened inside the
  predicted window, and it was **led by a new Tier 1**, which is what makes it a
  deal we could actually co-invest into.

**Note what the earlier version of this plan would have done.** Promoting on p90
would have fired in November or December and produced contact in December at best
— **six weeks before the round, not three months.** Triggering on the 180-day
horizon instead is the whole difference between hitting the goal and missing it.

**Total AI cost for this company across seven months: six scans plus one research
pass, well under $1.05 all in** (the scan table above gives the exact per-scan
figures). Everything else was free public data and arithmetic.

### 7.2 A company that fails the mandate screen

**Halden Compute** — strong company, Series B $18M closed March 2026, growing fast.
But the cap table is a regional fund plus angels; no Tier 1 anywhere, and the last
round was a flat extension.

**T0 fails on S3.** Recorded with the reason, and **never sensed.** Even a perfect
timing prediction wouldn't help: without a new Tier 1 leading, there is no
co-investment for us. This is the screen doing its job — it's why the sensed
population is a few hundred companies rather than a few thousand, and why the
running cost is what it is.

### 7.3 A company that should not be escalated

**Southgate Robotics** — 22 months past its Series A, well beyond its window.
A naive "overdue means due" model puts it at the top of the list.

The sensors disagree: headcount 64 → 57 over four months (**T8**), Head of Finance
departed in September (**T12**), three postings closed and none opened. The
distress branch fires — suppressed, flagged, no research pass, no partner brief.

Being right here is what makes the rest of the list worth reading.

---

## Part VIII — Data model

```js
radar: {
  entryPaths: [{ path: 'pitchbook-top10', at: '2026-08-02',
                 detail: 'Series B $32M closed 2026-02-10, lead <firm>' }],
  lastRound: 'Series B', lastRoundDate: '2026-02-10', roundSize: 32000000,

  relevance: { pass: true, excludedBy: null, excludedAt: null,
               matchedText: null, keepAnyway: false },

  mandate: { pass: true, geoPass: true, nextRoundInMandate: true,
             tier1OnCapTable: true, tier1Firms: ['<firm>'], top10VCFlag: true,
             newTier1LeadLikely: 'high', insiderRoundRisk: 'low',
             reasoning: '...', failReason: null },

  clock: { headcount: 81, costPerHead: 280000, estMonthlyBurn: 1890000,
           estCashOutDate: '2027-08', runwayMonths: 9.6,
           predictedWindowOpen: '2027-02',
           contactByDate: '2026-11-01', alertAtDate: '2026-10-15',
           assumptions: '...' },

  p180: 0.41, p90: 0.22, p180Delta: +0.09,
  predictedWindowStart: '2027-01', predictedWindowEnd: '2027-05',
  confidence: 'medium', familiesActive: ['preparation','narrative'],
  distressFlag: false, accessScore: 10,

  route: { firm: '<firm>', contactRecordId: '...', readyAt: '2026-09-16' },
  contactStatus: 'made', contactMadeAt: '2026-11-06', contactLeadDays: 92,

  ats: { provider: 'greenhouse', token: 'northwind' },
  checkedAt: '2026-11-14', state: 'contacted', lastResearchPassAt: '2026-10-08',
}
```

Subcollections: `signalSeries/{sensor}` (capped `{date, value}` arrays, one read
per sensor), `radarEvents/{id}` (typed triggers with dates and links),
`predictions/{id}` (append-only feature vectors — what makes calibration
possible).

The exclusion ruleset is a single top-level document, not per-company — one read,
cached, and the rules are shared:

```js
radarRules/current: {
  keywords:   [{ term: 'drug discovery', addedBy: 'oscar@…', addedAt: '…', note: 'off-thesis' }],
  categories: [{ value: 'Pharmaceuticals and Biotechnology', addedBy: '…', addedAt: '…' }],
  companies:  [{ slug: 'some-co', reason: 'founder conflict', addedBy: '…', addedAt: '…' }],
  required:   [],   // default empty — see the warning in §1.6
  updatedAt: '…',
}
```

**Keep the latest values denormalised on the company document.** A subcollection
read per row would repeat the full-collection N+1 that caused the last hub
performance fix.

---

## Part IX — Build phases

| Phase | Work | New spend | Acceptance |
|---|---|---|---|
| **0 · Foundations** | `deal_date` → `READ_SLUGS` → `DealInput` → `radar.lastRoundDate`; backfill from Attio; schema; `radar_state.py` as sole writer | none | Every radar company has a round + date, or a recorded reason |
| **1 · Mandate screen** | S1–S4; Tier 1 firm list matching against the investor columns; `newTier1LeadLikely` priors | none | Run over existing radar companies; **Oscar reviews the pass/fail split by hand** — this gate decides who we ever look at |
| **1b · Relevance rules** | Move `EXCLUDED_KEYWORDS` out of [`sectorRelevance.js`](hub-next/src/lib/sectorRelevance.js) into `radarRules/current`; word-boundary matcher; retroactive re-evaluation (T22); Radar-tab editor with **dry-run preview**, "Excluded (N)" section, restore, and "keep anyway" | none | Seeded from today's hardcoded list with identical results; adding a keyword drops matching companies with no deploy; preview counts match what actually happens |
| **2 · Capital clock** | `capital_clock.py` — burn, cash-out, window, `contactByDate`, `alertAtDate`, assumptions record | none | **Validate against ID8 holdings where real burn is known** |
| **3 · Filing sensors** | `sensors/filings_us.py` (EDGAR), `sensors/filings_uk.py` — daily; related-persons parsing to identify who led | **$0** | Detect a real round **before PitchBook records it**, and log the lead time in days |
| **4 · Hiring sensors** | ATS detection; `sensors/jobs.py` (Greenhouse/Lever/Ashby JSON); `sensors/headcount.py` (Apollo); `signal_extract.py` composition classifier | none | Classifier hand-validated on 30 postings; pre/post discriminator checked against 10 companies with known recent rounds. **Start sampling before the model is finished — expired postings are unrecoverable** |
| **5 · Hazard model** | `hazard.py` — kernels, p180/p90, two-family rule, hysteresis, distress branch. Pure functions, unit-tested | none | Full test suite; run over the population; **manually review top 20 and bottom 20 for face validity** |
| **6 · Research tier** | `raise_thesis.py` — one bounded call on Perplexity's cheap `sonar` tier (same tier Stage 0 already uses, not `sonar-deep-research`), **capped at $0.40**: adversarial contradiction check, `newTier1LeadLikely` assessment, route resolution, and the card text together, no separate synthesis call | ~$25–35/yr | 10 cards reviewed; contradiction pass must catch ≥1 real sensor false positive; **measure actual per-call cost against the $0.40 cap in the first 10 runs** |
| **7 · Hub surface** | Radar table (p180, contact-by date, contact status, window, Δ, family badges, mandate verdict); "Contact window open" pinned; signal timeline; partner brief | none | — |
| **8 · Intake hardening** | Routing rule (§1.5a) + backfill existing Series B; export staleness alarm; then export automation or API pull | licensing TBD | No silent intake failure possible |
| **9 · Calibration** | `calibrate.py` quarterly — **contact-by-T−3 hit rate**, calibration curve, Brier, top-decile lift, per-signal information gain, `newTier1LeadLikely` accuracy | none | Published internally. **Expect to delete sensors** |
| **10 · Social sensors** *(conditional)* | X, Reddit, deeper web diffing | ~$500–1,500/yr | **Only if Phase 9 shows headroom** |

**Phases 0–5 need no new vendor and no new spend** — free public APIs plus Apollo,
covering the two highest-value families. The scraping layer everyone reaches for
first is Phase 10, deliberately last.

---

## Part X — Operations

### The KPI

Not Brier score — the business goal, measured directly:

> **Contact-by-T−3 hit rate:** of the rounds that closed among mandate-passing
> watched companies, in what fraction did we have contact at least three months
> before the round opened?

Every filing detection (T1) records `contactLeadDays`, so this computes itself.
Misses get a reason from a fixed taxonomy — *signal arrived too late* / *no access
route existed* / *intro requested but never landed* / *company never passed the
threshold* — because each reason implies a different fix. A miss caused by a late
signal is a model problem; a miss caused by an intro that never landed is not.

Secondary: how often `newTier1LeadLikely` was right, scored from the Form D
related-persons list.

### Schedule

**Ledger jobs** — fixed rhythm, free, no analysis (§6.1):

| Job | Cadence | Scope |
|---|---|---|
| Filing check | daily | all mandate-passing companies |
| Job-board snapshot | weekly | all mandate-passing companies |
| Headcount | monthly | all mandate-passing companies |
| News + site diff | weekly / monthly | all mandate-passing companies |
| Tier 1 activity profiles | monthly | the Tier 1 firm list |

**Scan and action jobs** — per-company, adaptive (§6.2):

| Job | Cadence | Scope |
|---|---|---|
| **Scan runner** | daily job, picks up whatever has `nextScanAt <= today` | ~1–2 companies/day at 100 under management on average, bursting around the two mandatory sweep dates and around any company entering its critical window |
| Opening sequence | T+4mo, then T+6mo from round close | each new company |
| **Mandatory sweeps** | **~5 Sep and ~12 Jan** | every company, regardless of `nextScanAt` |
| Research pass | event-driven only, ≤1/company/30d | threshold crossings |
| Contact-deadline check (T16) | daily | anything with `contactByDate` inside 30 days |
| Partner brief | weekly | contact-window-open and contacted companies |
| Calibration | quarterly reporting; re-fit at 18–24 months | all predictions |

Dead zones apply to the scan runner but **not** to the filing check — a company can
close a round in August and we still want to know within 15 days.

### Infrastructure

**Cloud Run Jobs, not the Flask web service** — long-running and I/O-bound, and a
request deadline has already caused one production bug here. **No git commits from
any sweep** — a Cloud Build trigger on `main` redeployed the service mid-run once
already. Cloud Scheduler fires the jobs; Firestore stores the series.

### Cost

Public pricing, not billing data. Marginal only.

At **100 companies** under management:

| | Volume | Annual |
|---|---|---|
| Filing checks (EDGAR, Companies House) | 100/day | **$0** |
| Job boards (Greenhouse / Lever / Ashby public JSON) | ~5,200/yr | **$0** |
| Apollo headcount | 1,200/yr | within existing plan — verify credit limits |
| Routine scans (≤$0.15 each, hard-capped) | ~500/yr | **≤$75** |
| AI research passes (≤$0.40 each, hard-capped) | ~60–90/yr | **≤$25–35** |
| Cloud Run Jobs + Firestore | daily jobs, small docs | ~$20–40 |
| **Total, Phases 0–9** | | **~$120–150** |

**Every AI call in the system, routine or escalated, is now capped** — $0.15 for a
scan, $0.40 for a research pass, enforced in code, not just budgeted on paper. That
also means the two tiers keep the same *character*, not just a smaller number: the
escalation pass is still a real, separate check (adversarial contradiction, route
naming), it just runs on the cheap Perplexity tier instead of the deep-research
one.

Two things keep this flat as the list grows: the mandate screen removes most
candidates before any sensor runs, and **the expensive layer scales with
*escalations and scan count*, not with company count directly** — going from 100
to 300 companies roughly triples the free work, adds ~$150 of routine-scan cost
(bounded by the per-scan cap regardless of how busy any one company's ledger
gets), and adds ~$75–105 of research passes (bounded by its own cap, same logic).

### Risks

| Risk | Mitigation |
|---|---|
| Preparation signals are the only family with enough lead time for T−3 — if hiring data is thin, we can't hit the goal | Phase 4 validates ATS coverage **first**. A company with no public job board and no Apollo postings gets wider windows and lower confidence, stated on the card |
| Base rate is 5–8% per 90 days; most flagged companies won't raise in-window | Contact is framed on the company, not a raise, so a miss costs nothing |
| "Overdue" misread as bullish when it's distress | Explicit distress branch (§4.5) |
| Sensor breakage read as signal | T19: `unknown` ≠ `no change`; freshness on every card |
| AI-heavy burn under-modelled (compute > payroll) | Flag as a class; they raise sooner than the model says |
| `newTier1LeadLikely` is the hardest call in the system | Score it against Form D related persons every time (T1); it's the metric most likely to need recalibration |
| PitchBook API not licensable at sane cost | Drive-drop stays the pathway; staleness alarm removes the silent failure |

---

## Part XI — Acting: the three stages

| Stage | Trigger | Action | Contact? |
|---|---|---|---|
| **Prepare the route** | T14 · p180 ≥ 20% or any preparation signal | Identify the Tier 1 on the cap table, who we know there, whether the contact exists in Attio. Fix gaps now | **No** — internal only |
| **Make contact** | T15 · p180 ≥ 35%, mandate passes | Research pass → card → request the intro through the named route, **framed on the company, not on a raise**. Target: contact within 6 weeks | **Yes — this is the goal** |
| **Already known** | p90 rising, or T6/T10 process signals | We're in the conversation before the process starts. Brief partners, prepare to move | Maintain |

**Never open with "we hear you're raising."** Wrong, it's embarrassing and burns
the relationship; right, it's presumptuous. The prediction is for our
prioritisation, not the founder's ears — and a company that isn't raising is still
one we wanted to know.

Nothing sends automatically. The system decides who is worth an hour of someone's
attention this week; a person decides what to say.

---

## Part XII — Open decisions

0. **Scan cadence** — T+4 then T+5 confirmed, then computed (§6.2). Sign off on the interval table and the ×0.7 / ×1.4 capital-intensity modifiers, and on the two mandatory sweep dates (~5 Sep, ~12 Jan)?
0b. **Starting exclusion list** — keep today's hardcoded 16 keywords as the seed, or revise? Anything obviously missing (crypto/web3, gambling, cannabis, staffing, consumer social, defence primes…)? And does the *required*-keyword type stay off, as recommended?
1. **Contact lead target** — 3 months confirmed. Is 6 weeks the right allowance for working an introduction, or should the alert fire earlier still?
2. **p180 promotion threshold** — 35% proposed. Lower means earlier contact and more false starts; higher risks missing the deadline.
3. **Routing rule** — pure "Series B and below," or `Deal Date` + series so genuinely-live Series B rounds still get an immediate Stage 1 screen?
4. **Tier 1 firm list** — which firms count for S3? The existing Top 10 VC list, or a wider "firms we'd co-invest behind" list?
5. **S3 strictness** — hard exclude when no Tier 1 is on the cap table, or keep those companies at minimum sensing in case a Tier 1 arrives later?
6. **Existing companies** — re-file current Series B / Watchlist / previously-too-early companies to Radar, or is Radar forward-looking from the routing change onward?
7. **Cost-per-head assumptions** — sign off on §III's table, or supply real portfolio numbers (better).
8. **Alerts** — weekly digest, plus same-day on T15 (contact window opens) and T16 (deadline within 30 days)?
