# The Radar Signal Engine — Predicting When a Company Will Raise

> **Status:** system design, from first principles. Deliberately written before
> any consideration of what tooling ID8 currently owns — §10 does that mapping
> afterward, and nothing in §1–9 was shaped by it.
> **Role:** this doc holds the *mechanism reasoning* — why each signal works, and
> where the weights come from. The buildable plan is [RADAR_PLAN.md](RADAR_PLAN.md),
> which is authoritative on intake, sources, metrics, triggers, phases and cost.
> **Written:** 2026-07-28

---

## 1. What the system is actually for

**Question it answers:** *for each company we're watching, when will it next open a fundraise, and how confident are we?*

**Not** "how good is this company" — that's the fit rubric, already built and separate. Conflating the two is the mistake to avoid: a great company 4 months post-round is not actionable, and a mediocre one opening a process next month is not interesting. The system's whole job is the **timing axis**. Fit and access are separate axes that decide whether a well-timed company is worth acting on.

**Output per company**, and this is the contract everything else serves:

```
Anysphere
  P(opens within 180 days):         41%   ▲ from 18% six weeks ago   ← action trigger
  P(opens within 90 days):          22%                              ← urgency read
  Predicted window:                 Oct 2026 – Feb 2027
  Contact by:                       Jul 2026  (3 months before predicted open)
  Mandate screen:                   ✓ NA/Europe · next round B+ · Tier 1 on cap
                                    table · new Tier 1 lead likely: HIGH
  Confidence:                       medium (3 signal families, 2 independent)
  Capital clock:                    raised $28M Feb 2025 · est. burn $1.9M/mo
                                    · est. cash-out Jun 2027 · window opens Sep 2026
  Why now:
    • VP Finance role posted 11 weeks ago, still open        [F2, peak effect now]
    • Headcount 61 → 94 in 7 months (+77% annualized)        [F2]
    • Founder posted ARR milestone thread, 3rd in 6 weeks    [F3]
    • Two enterprise logos announced since May               [F3]
  Access route:                     Series A lead is a firm we co-invest alongside
                                    · partner-level contact already in Attio
  Recommended action:               request the intro this week, framed on the
                                    company · target contact by Jul 2026
```

The unit of value is that card. It's what gets forwarded to a partner. Everything upstream exists to produce it honestly.

**A hard constraint on the whole design:** the base rate of "raises in the next 90 days" for a random venture-backed company is roughly 5–8%. Even an excellent model gets top-decile precision to maybe 25–40%. **Most hot calls will not convert in-window.** That fact dictates the action design (§8): the recommended action on a hot company must be something that costs nothing when we're wrong.

---

## 2. First principles: a raise is a process, and processes leak

Signals aren't a grab-bag to be listed and weighted. A fundraise is a **sequence of internal steps**, each of which has observable exhaust, at a characteristic lead time. Design the sensors around the process, not around whatever happens to be scrapable.

| Phase | What the company is doing internally | What leaks, and where | Lead time |
|---|---|---|---|
| **Decision forming** | Board discussion; runway math; benchmarking | Almost nothing. Sometimes: a hiring freeze ends | T−12 to T−9 |
| **Story construction** | Building the metrics narrative and the data room | **Finance function build-out** (CFO, VP Finance, Controller, FP&A), data/analytics hires, senior GTM hires (CRO, VP Sales), recruiter hires | **T−9 to T−6** |
| **Market warming** | Making itself visible to investors before it needs to ask | Founder podcast/conference circuit, X threads quoting metrics, PR push (logo wins, partnerships, product GA, analyst mentions), website changes (press page, enterprise tier, case studies), existing investors amplifying | T−6 to T−3 |
| **Process running** | Bankers, first meetings, term sheets | Press leaks ("in talks to raise at $Xb"), Head of Corp Dev hire, independent board member added, amended certificate of incorporation authorizing new preferred shares | T−3 to T−0 |
| **Close** | Wire | **SEC Form D** (US, ≤15 days after first sale), **Companies House SH01** (UK, ≤1 month), press announcement (2–8 weeks later, timed) | T+0 |
| **Deployment** | Spending it | Job posting explosion, headcount step-up, office, brand refresh | T+1 to T+3 |

Two structural insights fall straight out of this table, and they're the ones that make the difference between a signal engine and a keyword alert:

**(a) The best window is T−9 to T−6, and it's observable through hiring composition.** Not hiring *volume* — composition. A company preparing to raise hires **narrow and senior**: a finance leader, a data hire, an exec GTM role. A company that just *closed* hires **broad and junior**: ICs across engineering and sales. Both look like "hiring is up" to a naive volume sensor, and they mean opposite things. Composition is the discriminator, and it's the single most valuable thing this system measures.

**(b) Our current fastest channel is our slowest.** The pipeline learns about rounds from a PitchBook export — which records a round weeks-to-months after close, and after press. Form D lands within 15 days and is free. The confirmation layer isn't a nice-to-have; it's a strict upgrade on how we learn a round happened at all.

### 2.1 Five signal families

Grouping by mechanism (not by data source) matters because **independence** is what makes a composite prediction trustworthy. Three signals from the same family are one signal with three names.

| | Family | Mechanism | Lead | Precision | Noise |
|---|---|---|---|---|---|
| **F1** | **Capital clock** | They raise when cash runs low. Arithmetic, not observation | 6–18mo | Low alone, essential as baseline | None — deterministic |
| **F2** | **Organizational preparation** | Building the apparatus a raise requires | 6–9mo | **High** | Low–medium |
| **F3** | **Narrative warming** | Manufacturing investor-visible momentum | 3–6mo | Medium | **High** |
| **F4** | **Process leakage** | The process itself becoming visible | 0–3mo | **Very high** | Low |
| **F5** | **Confirmation** | It already happened | 0 | Certain | None |

F5 is not a predictor and shouldn't be scored as one. Its two jobs are (1) reset the capital clock, (2) **label predictions for calibration** (§9). Without F5 the system can never learn.

### 2.2 The distress discriminator

The hardest failure mode, and one the current timing model explicitly admits it can't handle: **"well past its cadence window" is equally a sign of imminent raise and of dying.** Treating overdue as bullish is how you spend a partner's attention on a corpse.

The separator is F2's derivative:

| Overdue + | Reading |
|---|---|
| headcount growing, senior/finance hiring | **Imminent raise** — they waited to raise on strength |
| headcount flat, no hiring, quiet | **Zombie** — drop to minimum sensing, don't escalate |
| headcount declining, exec departures (esp. finance leaving), layoffs | **Distress** — raise probability *falls*; possible structured/down round or asset sale. Flag, never escalate as an opportunity |

This must be an explicit branch in the model, not an emergent weighting. Getting it wrong is worse than having no model.

---

## 3. The capital clock: runway, not cadence

Replacing "months since last round vs. stage-typical cadence" with actual arithmetic is the largest single accuracy gain available, and it needs no scraping beyond headcount.

Companies don't raise on a schedule; they raise when cash gets short. Cadence averages are a crude proxy for runway, and we can compute runway directly:

```
capital_in       = round size (known from intake)
burn_rate(t)     = headcount(t) × fully-loaded cost per head / 12
                   ... with headcount(t) interpolated from the sampled series
cash_out_date    = round_date + months until capital_in is consumed
raise_window     = [cash_out − 12 months, cash_out − 6 months]
```

Founders start a process with 9–12 months of cash and aim to close with 6. So the **window opens** at cash-out minus ~12 and the hazard peaks around cash-out minus ~8.

Fully-loaded cost per head is the one real assumption. Rough priors, to be refined per company from geography and business type:

| Company type | Fully-loaded $/head/yr | Note |
|---|---|---|
| US software, growth stage | $220–260k | Bay Area/NY skews high |
| European software | $130–180k | |
| AI/ML-heavy | $300–400k+ | compute is a second burn line, often larger than payroll |
| Hardware / deeptech / defense | $250k+ **plus** capex | payroll is a minority of burn; runway math is weakest here |
| Consumer with paid acquisition | payroll + marketing spend | marketing can dominate |

Worked example: raised $28M Feb 2025 at 45 heads, now 94 heads 17 months later. Average ~70 heads over the period at $240k = ~$1.4M/mo average, ~$1.9M/mo now. Consumed ≈ $24M. Remaining ≈ $4M, at $1.9M/mo ≈ **cash-out around Oct 2026**. Window opened around Oct 2025; they are *late*, and given they're still growing headcount hard, either a raise is already underway or there's revenue covering more burn than modeled. Both readings are actionable, and the arithmetic is what surfaces them — a cadence model would have said "17 months, inside the typical window, medium."

Where revenue is known or estimable, net burn replaces gross and the window pushes out. Where it isn't, gross burn is the conservative read, and the output should say which was used. **Every runway figure carries its assumptions on the face of the card** — a stated-assumption estimate is useful; a bare date that hides a $240k/head guess is not.

The AI-heavy row deserves emphasis given ID8's mandate: for a company training its own models, compute can exceed payroll, and headcount-derived burn will substantially *underestimate* it. Those companies raise sooner than the model says. Flag them as a class rather than pretending the arithmetic holds.

---

## 4. The prediction model: hazard, not score

A 0–100 heat score is the wrong object. It isn't falsifiable, can't be calibrated, and doesn't answer the question asked. The right object is a **hazard**: probability of the event occurring within a horizon.

```
P90(company) = 1 − exp( −h₀(clock) × Π ᵢ mᵢ(signalᵢ, ageᵢ) × 0.25 )
```

- **h₀** — baseline annualized hazard from the capital clock (§3), the only always-present term.
- **mᵢ** — a multiplier per active signal, itself a function of **how old the signal is**.

### 4.1 Signals have peak-effect delays, not just decay

This is the refinement that separates this from a weighted-sum score. A CFO hire is *more* predictive four months after it happens than the week it's announced — the hire exists in order to run a process that starts later. A press report saying "in talks to raise" is maximally predictive immediately and worthless nine months on.

So each signal gets a **kernel** over time-since-event, not a decay:

| Signal | Peak effect at | Multiplier at peak | Shape |
|---|---|---|---|
| Finance leader hired / posted (CFO, VP Finance) | T+4mo | ×2.5 | slow rise, peak 3–7mo, fade by 12mo |
| Head of Corp Dev hired | T+2mo | ×2.2 | sharp, fades by 6mo |
| Press: "in talks to raise" | immediate | ×6.0 | spike, halves every 6 weeks |
| Independent board member added | T+2mo | ×1.8 | fades by 8mo |
| Headcount growth >40% annualized | concurrent | ×1.6 | tracks the derivative continuously |
| Senior GTM hiring burst (CRO/VP Sales) | T+3mo | ×1.4 | broad, fades by 9mo |
| Recruiter/TA hiring | T+3mo | ×1.3 | broad |
| Founder public cadence ≥2× baseline w/ metrics claims | T+2mo | ×1.5 | fades by 5mo |
| Major product GA / launch | T+2mo | ×1.4 | fades by 6mo |
| Marquee customer or partnership announced | T+2mo | ×1.3 | fades by 6mo |
| Enterprise pricing tier / SOC 2 / upmarket web changes | T+4mo | ×1.2 | slow |
| Existing lead investor closed a new fund <12mo ago | flat | ×1.2 | constant while true |
| Last round was a bridge/extension | flat | ×1.5 | constant (and lowers fit) |
| Runway model: <9 months cash remaining | flat | ×2.2 | folded into h₀ where clock data is good |
| **Layoffs in last 90 days** | immediate | **×0.6** | + distress flag |
| **Finance leader departed** | immediate | **×0.5** | + distress flag |
| **Headcount declining >10%** | concurrent | **×0.4** | + distress flag |

**Every number above is a hand-set prior.** They encode the mechanism reasoning in §2 and nothing more. They are wrong in detail and will be replaced by calibrated values (§9). Stating them explicitly is what makes them *correctable* — the point is that the model is legible, not that it starts accurate.

### 4.2 Guardrails against false hots

Three rules, all deterministic:

1. **Two-family rule.** `hot` requires active signals from **≥2 distinct families**. Four job postings are one signal. This is the main defense against a single noisy sensor manufacturing conviction.
2. **Composite cap.** Multipliers cap at ×8 total, and no single signal may take a company from cold to hot on its own — except a hard F4 press report, which is allowed to, because it deserves to.
3. **Hysteresis + dwell.** Promotion at P90 ≥ 30%, demotion only below 20%, minimum 30 days in a tier. Without this the system flickers and nobody trusts it.

### 4.3 Confidence, reported separately

Probability and confidence are different things and must not be blended. A 30% from three independent families with fresh data means something a 30% from one stale sensor does not.

`confidence = f(number of independent families, freshness of newest signal, sensor coverage of this company)`

A stealth company with no observable exhaust should return **low confidence and a wide window**, not a low probability. Absence of signal is not evidence of absence — and a system that reports it as such will systematically ignore exactly the quiet, high-quality companies worth finding.

---

## 5. Sensing architecture: time series, not lookups

**The central design property: every sensor stores a time series, and the prediction reads derivatives.** A single scrape of a LinkedIn page is nearly worthless. Twelve monthly samples showing 40 → 94 heads with a VP Finance role opening in month 9 is the entire ballgame.

Three consequences:

1. **The system is worth little on day one and compounds monthly.** There is no shortcut — the data asset must be accumulated forward. Starting collection is the highest-priority action, ahead of any modeling refinement.
2. **Sensors must be cheap enough to run on everyone, continuously.** A sensor too expensive to run monthly on the whole watch list produces no derivative and therefore no signal.
3. **Historical backfill is mostly impossible.** Expired job postings and deleted posts are gone. Headcount history is available from some vendors; filings and news are archived and *are* backfillable. Design assuming partial history at best.

```
┌─ TIER 1: SENSORS ──────────── continuous, deterministic, no LLM ────────────┐
│  filings/registries · job boards · headcount · web diff · social · news     │
│  → append to per-company, per-sensor time series                            │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─ TIER 2: EVENT EXTRACTION ─── deterministic diffing, no LLM ───────────────┐
│  derivatives + classification: new senior finance role? headcount           │
│  inflection? cadence step-change? filing appeared? → typed events           │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼
┌─ TIER 3: HAZARD ───────────── plain arithmetic, auditable, no LLM ─────────┐
│  capital clock h₀ × Σ signal kernels → P90, window, confidence, band        │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ▼  (only on material change or hard event)
┌─ TIER 4: REASONING ────────── expensive, event-driven only ────────────────┐
│  deep research pass over the signal timeline → the raise-thesis card,       │
│  contradiction checks, access path, recommended action                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

Tiers 1–3 contain **no language model at all**. That's deliberate: the prediction must be reproducible, auditable, and cheap enough to run on thousands of companies weekly. The LLM's job is to *explain and contextualize* a number that was computed deterministically — never to produce the number. This is the same separation that already proved necessary between deterministic timing and model overlay, extended to its logical end.

### 5.1 Sensor specification

| Sensor | Emits | Family | Refresh | Cost profile |
|---|---|---|---|---|
| **Securities filings** (US Form D; UK share-allotment filings) | new offering filed, amount, date | F5 (+F4 on amendments) | **daily, whole universe** | free |
| **Job postings** | count, titles, seniority mix, function mix, first-seen/last-seen per role | **F2** | weekly (warm+) / monthly (cold) | cheap |
| **Headcount** | employee count by function | **F2** | monthly | cheap |
| **Exec changes** | joins/departures at VP+ , esp. finance | **F2/F4** | monthly | cheap |
| **Founder + company social** | post cadence, metrics claims, hiring posts, investor engagement | F3 | weekly (warm+) | cheap, noisy |
| **News & press** | funding-rumor language, launches, logos, layoffs | F3/F4/F5 | weekly | cheap |
| **Website diff** | careers/pricing/press/case-study/trust-badge changes | F3 | monthly | very cheap |
| **Community** (forums, technical communities) | mention volume, sentiment | F3 | monthly | cheap, very noisy |
| **Review/employee sentiment** | rating trend, layoff chatter | F2-negative | monthly | cheap |
| **Investor-side** | did their lead close a new fund | F1-adjacent | quarterly | cheap |

Notes on what's genuinely available vs. wishful:

- **US pre-close filings are not cheaply harvestable.** The amended certificate of incorporation authorizing new preferred shares — a near-deterministic T−1mo signal — sits in Delaware behind paid, per-document retrieval with no bulk API. Real signal, not economically accessible at scale. Don't design around it.
- **UK is the exception in Europe.** Share-allotment filings are free, structured, and land within a month. The rest of Europe is patchy and mostly not worth the integration effort per country.
- **Social is weakest exactly where the mandate is strongest.** B2B infrastructure and defense-adjacent companies emit little useful social signal; consumer and dev-tools emit plenty. Weight F3 down for enterprise/infra, and never let it carry a hot call alone.

---

## 6. When to scan: three independent clocks

This is where a single cadence timer fails, and it fails for a structural reason: **different sensors have different natural refresh rates, and the expensive layer shouldn't be on a timer at all.**

### Clock 1 — Confirmation (free, daily, everyone)

Filing feeds run daily across the entire universe, however large. Cost is ~zero, so there is no reason to ration it. This clock guarantees we **never miss a close**, which resets capital clocks and generates calibration labels. It is the floor of the system: even a company we've written off stays on this clock forever.

### Clock 2 — Sensors (cheap, per-sensor rate × attention tier)

Each sensor refreshes at the rate its underlying quantity actually changes — job postings weekly, headcount monthly, website monthly — **multiplied by an attention tier** derived from the company's own current hazard:

| Attention tier | Membership | Sensor suite | Cost/co/mo |
|---|---|---|---|
| **A — Active watch** | P90 ≥ 20%, or fit×access high | full suite, weekly | highest |
| **B — Standard** | fit clears the bar, P90 5–20% | jobs + headcount + news monthly | moderate |
| **C — Ambient** | everything else | filings only, daily | ~zero |

The dish points itself: rising hazard pulls a company into a denser sensor suite, which yields better signal, which sharpens the hazard. Falling hazard releases the budget. **Nobody is ever dropped** — Tier C is free, so the universe can hold thousands and still catch every close.

### Clock 3 — Reasoning (expensive, event-driven, never on a timer)

The deep pass fires **only** on:
- a **hard event** — filing appears, finance leader hired/departed, press rumor, layoffs; or
- **material hazard movement** — P90 crosses a band boundary, or moves ≥10 points; or
- **promotion to hot** — always gets a fresh pass before any human is asked to act; or
- a **staleness floor** — no deep pass in 180 days *and* the company is Tier A (guards against a slow drift the event rules miss).

Rate-limited to one pass per company per 30 days. This inverts the usual design: cheap sensing is scheduled, expensive reasoning is reactive. A quiet company costs approximately nothing indefinitely; a company doing interesting things pulls attention automatically.

### Anti-thrash and budget control

- Hysteresis and dwell time as in §4.2.
- Hard monthly cost ceiling per attention tier; when a sweep would exceed it, the sweep **logs what it dropped** rather than silently truncating.
- Sensor failures are recorded as `unknown`, never as `no change` — a scrape that 403s must not read as "headcount flat."

---

## 7. Which companies to watch

> **Membership is fixed by policy** (Oscar, 2026-07-28): Radar contains what the
> Top 10 VC and Qualified deals workflows deliver at Series B or below, and
> nothing else. See [RADAR_PLAN.md](RADAR_PLAN.md) Part I. This section is therefore about
> **ranking attention within that set**, not about selecting into it.

"Watch the best companies" is a budget-allocation problem, and it's separable from prediction: **hazard says *when*, this says *whether we care*.**

```
watch_priority = fit_score × access_multiplier × check_size_fit
```

- **fit_score** — the existing four-dimension Stage 0 rubric. Already built, and applies to any company; nothing about it depends on where the company came from.
- **access_multiplier** — derived **per deal from the intake row**: the `Lead/Sole Investors`, `New Investors` and `Investors` columns (resolved to linked Attio Company records) plus the `Top 10 VC` flag. A firm we co-invest alongside on the cap table ≫ a known institutional investor ≫ a warm contact in Attio. **Nothing is not a low score — it's a hard exclusion** (see below).
- **new-Tier-1-lead likelihood** — will the *next* round be led by a new outside Tier 1, or done internally? Access and mandate fit are different questions and can point opposite ways: an existing Tier 1 is great for getting in front of the company and no guarantee the round qualifies for us. See `RADAR_PLAN.md` §1.4.

**Since ID8 co-invests, the mandate screen is a gate rather than a weighting** (Oscar, 2026-07-28): NA/Europe, next round Series B+, a Tier 1 already on the cap table, and not structurally an insider round. A company failing it is never sensed at all — perfect timing on a company we can't co-invest into is worth nothing. That gate is also the main cost control, since it removes most candidates before a single sensor runs.
- **check_size_fit** — will their next round have room for our check at our stage? A company whose next round is a $400M growth round led by a crossover isn't accessible regardless of heat.

`watch_priority` sets the attention tier (§6, Clock 2). Hazard sets urgency. **Hot Radar is the intersection**: high hazard **and** high watch priority.

At the volumes the membership rule implies (hundreds, not thousands), the tiering in §6 can collapse to one sensor suite run on everyone — `watch_priority` then only orders the hot list and the partner brief.

A high-hazard company with no access path isn't a deal, it's market news — worth logging, not worth a partner's attention. Making access constitutive of "hot" rather than a footnote is what keeps the hot list short and credible, which is the only reason anyone will keep reading it.

---

## 8. What happens when a company goes hot

Given §1's precision reality — most hot calls won't convert in-window — the action design must make being wrong free.

**The escalation, in order:**

1. Fresh Tier-4 reasoning pass → the raise-thesis card (§1).
2. **Contradiction check** before any human sees it: does the reasoning pass find anything that *invalidates* the sensor read? (The "VP Finance" hire was a backfill. The headcount jump was an acquisition. The "logo win" was a pilot.) An adversarial pass, not a confirmatory one — the sensors will be fooled sometimes and the cheapest place to catch it is here.
3. **Distress check** (§2.2). Growing or shrinking? Never escalate a shrinking company as an opportunity.
4. **Access resolution** — name the specific path from the deal's own investor columns and our Attio contacts: which investor on the cap table, which contact, which introduction. A hot card without a named route is incomplete.
5. **Recommended action, matched to lead time** — and this is the part that makes false positives costless:

| Predicted window | Action | Why it's safe when wrong |
|---|---|---|
| 6+ months out (early F2 signal) | **Internal only** — identify the Tier 1 on the cap table, who we know there, whether the contact exists. No approach yet | Nothing external happens, so nothing can be wrong |
| **~4.5 months out (P180 threshold)** | **Warm introduction through the named route, framed around the company, not a raise.** Target contact within 6 weeks, i.e. by T−3 | If they're not raising, we've met a good company early |
| 0–3 months, F4 evidence | We should already be known. Brief partners, prepare to move | Only reached when a process is genuinely visible |

**The action horizon is P180, not P90.** The goal is contact by T−3 (Oscar,
2026-07-28) and an introduction takes 4–6 weeks to work, so promoting on a 90-day
probability systematically delivers contact *after* the deadline. P90 is the
urgency read: high P90 with no contact yet is a flagged miss, not a hot lead.

The framing rule matters: **never open with "we hear you're raising."** When wrong it's embarrassing and it burns the relationship; when right it's presumptuous. Lead with interest in the company. The prediction is for *our* prioritization, not for the founder's ears.

6. **Partner brief** — hot companies with a named access path collect into a periodic digest for partners, because that's the workflow you actually described: we think this raises soon, here's our route, here's what we'd want from you.

Nothing in this ladder moves a company's stage or sends anything automatically. A hazard model is not strong enough evidence to put mail in a founder's inbox; it's strong enough to decide who a human spends an hour on this week. Every send stays a drafted action someone clicks.

---

## 9. Calibration: the part that makes it improve

Without this the system is a pile of opinions in a table. With it, it becomes a proprietary, improving asset — and this is the genuinely defensible piece.

**The mechanism is already built into the design:** Clock 1 (§6) observes every close for free, which means **every prediction gets an automatic label**. No manual data collection.

1. **Log every prediction** with its full feature vector — every active signal, its age, the hazard, the window, the confidence.
2. **When a round closes**, score the predictions made 90/180/270 days prior.
3. **Metrics that matter:**
   - **Calibration curve** — do our 30% predictions happen ~30% of the time? A well-calibrated 30% is far more useful than an overconfident 60%, because it can be acted on proportionately.
   - **Brier score** overall and by segment (stage, geography, sector).
   - **Lift over base rate** in the top decile — the actual business question: is watching this list better than watching randomly?
   - **Per-signal information gain** — which sensors earn their integration cost. Expect to *delete* sensors. Being able to justify deleting one is worth as much as adding one.
4. **Re-weight quarterly.** Hand-set priors → fitted coefficients. Stay with a legible hazard model (~15 covariates) rather than reaching for opaque ML; at the volume of rounds observable here, a hand-fitted hazard model is both the honest statistical choice and the one whose output a partner will trust.
5. **Volume check:** ~500 monitored companies yields ~100–200 observed rounds/year. Enough to calibrate a dozen-odd coefficients coarsely within 12–18 months. Not enough for anything deeper — and pretending otherwise is how you get a model that looks sophisticated and predicts nothing.

**Honest limitation on backtesting:** we cannot reconstruct most of this history. Expired job postings and deleted social posts are unrecoverable; filings, news, and some headcount history are archived and *can* be backfilled. So a partial retrospective is possible on F1/F4/F5, and F2/F3 must be validated forward. This is the strongest argument for starting collection immediately regardless of how much of the model is finished: **every month of delay is a permanently lost month of training data.**

---

## 10. Now the adaptation: what this needs vs. what exists

Design above stands on its own. Mapping it onto reality:

| Layer | Exists today | Gap |
|---|---|---|
| Fit scoring (4-dim) | ✅ Stage 0 rubric, built | none |
| Deep reasoning (Tier 4) | ✅ Perplexity sonar-deep-research + Claude synthesis | prompt for signal-timeline reasoning is new |
| Capital clock inputs | ⚠️ round size + date come in from the PitchBook export but **`deal_date` is never read back** into the pipeline | plumbing ([RADAR_PLAN.md](RADAR_PLAN.md) Phase 0) — blocks everything |
| **Headcount + job postings (F2)** | ⚠️ Apollo is already licensed and exposes org headcount and live job postings | wire it up; verify seniority/function granularity is enough for the composition rule — that rule is F2's whole value |
| Filings (F5, Clock 1) | ❌ | US Form D and UK allotment feeds are **free and unmetered** — highest value per unit of effort in the entire design |
| Social / community / web diff / reviews (F3) | ❌ | needs a scraping vendor (Bright Data is the obvious fit and is available as tooling, unkeyed today). **Lowest priority** — noisiest family, weakest exactly where the mandate is |
| News (F3/F4) | ⚠️ Perplexity can retrieve it, but not as a cheap repeatable weekly sensor | a search-API sensor, or accept a monthly Perplexity pass |
| Time-series storage | ❌ | Firestore subcollections per sensor; keep the latest computed hazard denormalized on the company doc so list views stay one read (the hub perf lesson is directly relevant) |
| Scheduling | ⚠️ Cloud Scheduler + Cloud Run exist | sweeps belong in a **Cloud Run Job**, not the Flask web service — these are long-running and I/O-bound, and request deadlines have already bitten this pipeline once |
| Calibration store | ❌ | append-only prediction log + a quarterly scoring script |

**Build order implied by the design, not by convenience:**

1. **`deal_date` plumbing + capital clock.** Unblocks everything; needs no new vendor. Produces a real runway estimate on day one.
2. **Clock 1 filing feeds.** Free, immediately better than PitchBook at detecting closes, and starts generating calibration labels from day one.
3. **F2 via Apollo** — headcount + job postings, monthly samples, composition classification. This is the highest-value predictive family and it runs on a subscription already paid for. **Start sampling before the model is finished** — the series is the asset.
4. **Tier 2/3 event extraction + hazard model** with hand-set priors, run over whatever history has accumulated.
5. **Hub surface + partner brief.**
6. **F3 sensors** (social, web diff, community) only after 2–5 are running and the calibration loop can actually tell whether they add information.

Note that steps 1–4 need **no new vendor at all**. The scraping layer everyone reaches for first is step 6, and by then there'll be evidence about whether it's worth paying for.

---

## 11. Decisions this design needs

1. ~~**Prediction horizon.**~~ **Settled:** P180 is the action trigger (contact by T−3 requires it), P90 is the urgency read. See §8.
2. ~~**Universe size.**~~ **Settled:** the two sourcing workflows at Series B or below, nothing else ([RADAR_PLAN.md](RADAR_PLAN.md) Part I). Remaining sub-question: does an existing Watchlist or previously-passed-as-too-early company get re-filed to Radar, or is Radar strictly forward-looking from the routing-rule change onward?
3. **Burn assumptions.** Sign off on the $/head priors in §3, or supply better ones from the portfolio's real numbers — you have actual data from holdings that beats any public prior.
4. **Social sensing.** Build it (needs a scraping vendor and a ToS decision), or run F1/F2/F4/F5 only? The design deliberately survives without F3.
5. **Distress handling.** Silent drop, or a separate "watch for a structured/secondary opportunity" lane? A distressed in-mandate company with a Tier 1 cap table is sometimes an opportunity of a different kind.
6. **Partner brief cadence** — weekly digest, or event-driven the moment something goes hot with a named access path?
