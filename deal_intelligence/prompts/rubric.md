<!-- The real ID8 rubric (v4, July 2026). Injected via rubric.rubric_text(),
which splices each dimension's fixed subcategory anchor tables into its
<!-- SUBCATEGORIES: <key> --> marker below, generated from PARAMS in
rubric.py -- that file is the single source of truth for subcategory keys,
titles, and anchor text. Keep dimension keys in sync with PARAMS. -->

# ID8 Deal Fit Rubric (v4)

Score each of the six dimensions below from 1 to 4. All six -- Lead / Round
Dynamics, Founder / Team Quality, AI Score, Terms, Fundamentals, Return
Potential -- sit at **exact parity, ~16.7% each**. Terms is a normal scored
dimension now, not a gate: bad terms drag the average like anything else,
they no longer unilaterally kill a deal (see "Hard auto-pass vs. soft pass"
below).

A dimension's score is not a holistic judgment call. Every dimension has a
fixed, standardized subcategory checklist (below); each subcategory gets its
own real 1-4 score against its own fixed anchor rubric, and the dimension
score is the mean of its subcategory scores, computed downstream -- not a
number you choose directly. Report both:

- **Raw average** -- plain mean of the six dimension scores.
- **Weighted average** -- the rubric's actual verdict; this is what gates a
  deal to deep research (see stage1_fit.md's thresholds). Identical
  computation to the raw average at this rubric version, since all six
  dimensions sit at equal weight -- reported separately because the
  underlying math (and the field names downstream) treat them as distinct,
  and because a future reweighting should not require a schema change.

| Dimension | Weight | What It Measures |
| --- | --- | --- |
| **Lead / Round Dynamics** | 16.7% | GP tier, new vs. re-up (verified), source-VC structural constraint, domain-strategic signal, direct access |
| **Founder / Team Quality** | 16.7% | Track record, domain authority, execution history, integrity |
| **AI Score** | 16.7% | Depth of AI moat: pure-play vs. data advantage vs. feature wrapper. No meaningful AI component is still a hard auto-pass; otherwise scored on the same curve as everything else. |
| **Terms** | 16.7% | Carry, upfront fee, structure. Scored on the same curve as everything else -- see "Hard auto-pass vs. soft pass" below for what changed. |
| **Fundamentals** | 16.7% | Revenue, growth, NDR, burn, capital efficiency, moat strength |
| **Return Potential** | 16.7% | Realistic MOIC and IRR trajectory, secondary-market demand corroboration -- no valuation caps |

## Missing data is not the same as bad data

This now applies at the subcategory level, since that's where scoring
actually happens -- a subcategory score of 1 must mean its anchor is
*confirmed* true, not "we couldn't find a number." Several subcategory
anchors below are written specifically so that missing or undisclosed data
lands on a 2, not a 1:

- Revenue, NDR, burn, or LTV/CAC not publicly disclosed -> work the research
  harder before conceding the gap. First, search press/funding coverage and
  Crunchbase/PitchBook-style estimates thoroughly. Second, check founder/exec
  podcast appearances, conference talks, and interviews for informally-stated
  metrics. Third, if a real number still isn't findable, triangulate an
  `[ESTIMATED]` range: carry forward the revenue multiple implied by a prior
  disclosed round (revenue at that round's valuation) to the current
  valuation, cross-checked against a second estimate from comp-set revenue
  multiples applied to the current valuation. Report both when they diverge
  rather than forcing one number. An `[ESTIMATED]` figure scores 2, 3, or 4 on
  its own merits -- never 1, a 1 is reserved for a *confirmed* bad number --
  and caps Diligence Confidence at MEDIUM, never HIGH. Only write
  `[NOT PUBLIC]` and land on a flat 2 as the last resort, when no prior-round
  data or usable comps exist at all; even then, let moat/defensibility,
  business model quality, and press-evidenced impact/scale (enterprise logos,
  market penetration, analyst characterization of traction) inform the score
  rather than just excusing a default 2. This is not the same fact pattern as
  a company that discloses genuinely weak numbers (sub-$5M ARR, sub-40%
  growth), which *is* a real 1. The distinction is disclosure, not existence:
  a pre-revenue or pre-commercial company (nothing to disclose, nothing to
  estimate from) is a genuine weak score, not a data-availability gap.
- Founder background unverifiable (thin press, no LinkedIn signal) -> lands
  on 2, flag `[unverified]`.
- Non-Tier-1 lead at Series B+ -> a real, known signal (not missing data),
  deliberately anchored at 2 rather than 1 so it drags the dimension mean
  rather than tanking it outright.

Score 1 is reserved for a *confirmed* disqualifying fact at the subcategory
level. When a dimension lands low because of one or more confirmed 1s within
it, say so in the evidence, and note in the deal-level rationale whether any
of them is one of the hard auto-pass triggers below.

## Dimension anchors

Each dimension section below gives two things: an overall 1-4 anchor table
(useful framing for what a strong vs. weak dimension looks like holistically)
and the fixed subcategory checklist that actually produces the score. Work
every subcategory; the dimension number is their mean, not a separate call.

**Lead / Round Dynamics (16.7%)** -- the primary first-filter signal. A
Tier 1+ fund leading with new money at Series B+ is what brings a deal into
the ID8 funnel; everything else is evaluation on top of that signal. Always
note `NEW` (first time on the cap table) or `RE-UP` (existing investor
increasing position).

| Score | Anchor |
| --- | --- |
| 4 | New-money lead from a Tier 1+ firm, primary, Series B+. Direct co-invest access confirmed. The cleanest signal ID8 acts on. |
| 3 | Two paths: a Tier 1 VC re-upping with strong conviction at Series B+ with direct access, OR a Domain-Strategic institutional lead (see below) -- mark this path `3*`. |
| 2 | Non-Tier-1 VC lead at Series B+, or any lead at Series A or earlier (stage always caps at 2). Soft pass via weight drag, not a kill. |
| 1 | **(hard auto-pass)** Insider bridge, anonymous SPV, CVC with no strategic relevance, or secondary with no credible access path. |

*Tier 1+ (Score 4 lead):* Sequoia · General Catalyst · Accel · Khosla
Ventures · Founders Fund · Benchmark · Index Ventures · Thrive Capital ·
ICONIQ Capital · Union Square Ventures · Bessemer · Lightspeed · Bain Capital
Ventures

*Tier 1 (Score 3 lead):* Andreessen Horowitz · Kleiner Perkins · Insight
Partners · IVP · TCV · Ribbit Capital · Notable Capital (fmr GGV) · New
Enterprise Associates · Dragoneer · Battery Ventures · Valor Equity ·
Addition · BOND Capital · Oak HC/FT · Coatue · Lux Capital · 8VC · Menlo
Ventures · Greenoaks Capital · DST Global. Under internal revisit -- treat as
Tier 1 but flag `[list under revisit]` in the evidence: Spark Capital ·
Greylock · First Round · Firstmark · Greycroft · GV.

*Domain-Strategic leads (Score 3\*):* a large institutional player whose core
business IS the market the company operates in -- asymmetric category
knowledge makes their entry a strategic validation signal, not a financial
one. Founding precedent: NYSE/ICE leading Polymarket's $600M round (the
exchange IS the prediction-market venue). Other qualifying patterns: Nvidia
leading an AI infrastructure company, a major bank leading a fintech, a
health system leading a clinical AI company. Generic corporate CVCs and
regional funds do not qualify -- there must be genuine domain asymmetry.

**Backtest calibration (ID8 Growth Opportunities Fund I deck, p.14 --
"Quantitatively Validated Systematic Investment Process").** ID8's own
backtest against the broader Series B/C/D universe validates new-money Tier-1
leads specifically -- it says nothing about re-up leads:

| Stage | New-money Tier-1 avg MOIC | Full stage universe avg MOIC |
| --- | --- | --- |
| Series B | 14.3x | 6.4x |
| Series C | 7.0x | 4.2x |
| Series D | 7.8x | 3.8x |

Before scoring a re-up lead at the same tier as new money, verify via cap
table history or prior-round disclosures that it is in fact a re-up, not an
assumed one -- ID8's own data validates new money specifically, not re-ups
broadly. A re-up claim taken at face value from a press release or company
statement, with no corroborating cap table evidence, should be flagged in the
evidence rather than scored as if confirmed.

**Subcategory checklist:**

<!-- SUBCATEGORIES: lead_round_dynamics -->

**Founder / Team Quality (16.7%)** -- scores the people independently of
product metrics.

| Score | Anchor |
| --- | --- |
| 4 | Serial founder with a meaningful exit or clear trajectory, deep domain authority, track record recruiting top talent, credible operators on the board/cap table. |
| 3 | First-time founder with elite pedigree (FAANG, top-tier academic, relevant domain), strong co-founder complement, recruiting credibly. |
| 2 | Capable but unproven in this specific domain; execution risk real; visible team gaps that may be addressable. Also the landing spot when background is genuinely unverifiable. |
| 1 | **(hard auto-pass)** First-time founders with no domain expertise, no credible signal, key roles unfilled, or verified negative history in the cap table or founder background. |

Signals to look for: prior exits or companies scaled to $100M+ ARR ·
LinkedIn headcount growth as a recruiting proxy · quality of existing
investors/advisors · founder presence in press, conferences, technical
writing · co-founder dynamics.

**Subcategory checklist:**

<!-- SUBCATEGORIES: founder_team_quality -->

**Fundamentals (16.7%)** -- moat strength and competitive positioning ·
valuation vs. revenue and margins · capital efficiency · sector disruption
risk. A revenue multiple vs. comp set is mandatory in every screen: search
hard for a real disclosed number first; if none exists, triangulate an
`[ESTIMATED]` range (prior-round multiple carried forward, cross-checked
against comp-set multiples applied to the current valuation) per the
estimation method above. Only fall back to `[NOT PUBLIC]` when estimation
genuinely isn't possible.

| Score | Anchor |
| --- | --- |
| 4 | $50M+ ARR, 100%+ YoY growth, NDR >130%, LTV/CAC >5x, burn <20% of revenue. Strong defensible moat, sector not at acute disruption risk. |
| 3 | $25M+ ARR, >70% growth, NDR >110%, LTV/CAC >3x, burn <50% of revenue. Moat real but moderate. Valuation defensible vs. public comps. |
| 2 | Early traction, some positive signals, most metrics below threshold -- OR an `[ESTIMATED]` range lands below the $25M/70%-growth bar -- OR no real number or usable estimate exists at all (`[NOT PUBLIC]`, last resort). Flag Diligence Confidence LOW when this 2 reflects a data gap with no usable estimate, MEDIUM when it reflects a genuine `[ESTIMATED]` figure. |
| 1 | **(hard auto-pass)** *Confirmed* sub-$5M ARR, sub-40% growth, NDR <100%, LTV/CAC <2x, burn >100% of revenue -- not merely undisclosed, and never reached via an `[ESTIMATED]` figure alone. Pre-revenue/pre-commercial companies with nothing to disclose also land here; that is a real gap, not a data-availability one. |

An `[ESTIMATED]` figure can land any of scores 2-4 depending on where it
falls against these anchors -- it is never itself a 1, and it caps Diligence
Confidence at MEDIUM (see "Missing data is not the same as bad data" above).

**Subcategory checklist:**

<!-- SUBCATEGORIES: fundamentals -->

**Return Potential (16.7%)** -- no valuation caps. Score on realistic
MOIC/IRR given entry price, growth rate, dilution, and exit path. Ask what
the company must achieve at this entry price for ID8 to return 6x, and
whether that's the base case or the bull case. Model at least two future
rounds of dilution (~20-25% each) before exit; for secondaries, calculate net
IRR inclusive of any upfront access fee.

| Score | Anchor |
| --- | --- |
| 4 | 6x+ MOIC / 30%+ IRR as the *base* case, not the bull case. Exit path visible, meaningful downside protection. |
| 3 | 3-6x MOIC / 20-30% IRR. Reasonable base case, some execution risk, entry justified but projections require discipline. |
| 2 | 2-3x MOIC / 10-20% IRR. Below venture scale -- competition too intense, entry too high, or TAM too narrow to reach 6x in the base case. |
| 1 | **(hard auto-pass)** Below 2x MOIC / below 10% IRR. Meaningful capital-loss risk; does not meet ID8's minimum return threshold. |

**Position-level calibration (deck p.21, as of May 29, 2026).** Live anchor
points for reasoning about realistic MOIC/IRR, not just the abstract
6x/base-case framework:

| Company | MOIC | IRR | Exit / Status | Hold |
| --- | --- | --- | --- | --- |
| Aven | 2.0x | 39.7% | Active | -- |
| Base Power | 3.0x | 459.0% | Active | -- |
| CoreWeave | 2.6x | 574.5% | IPO | 6 mo |
| Groq | 4.7x | 205.4% | M&A | 17 mo |
| Scale AI | 2.0x | 114.3% | M&A | 11 mo |
| Replit | 3.0x | 364.8% | Active | -- |
| Together AI | 2.3x | 99.0% | Active | -- |
| Saronic | 1.0x | -- | At cost, new | -- |
| Polymarket | 1.2-1.3x | 317.6% | Active | -- |
| Reflection AI | 1.0x | -- | At cost, new | -- |

Manager-level blended: 2.2yr average hold, 1.9x MOIC, 158.3% IRR.

**Subcategory checklist:**

<!-- SUBCATEGORIES: return_potential -->

**AI Score (16.7%)** -- does AI constitute the company's actual moat, or is
it a feature layer a foundational-model update could replicate? Test: could
this product become a plugin or default feature of Claude, GPT, or Gemini
without material loss? If yes, it scores 2 or below. Scored and weighted at
parity with the other dimensions -- but its bottom anchor is still a hard
auto-pass, exactly like Lead / Round Dynamics' bottom anchor: a real 1-4
score is required either way, and "no meaningful AI" ends the deal on its own
regardless of how everything else scores.

| Score | Anchor |
| --- | --- |
| 4 | Pure-play AI. Architecture, proprietary data flywheel, or fine-tuned model is defensible and the core moat -- cannot be trivially replicated by a model update. |
| 3 | AI-enabled with structural advantage: AI materially drives margin structure, data compounding, customer value prop, or distribution. Includes vertical AI with regulatory/workflow moats (health AI, compliance). |
| 2 | AI-adjacent / feature layer. Uses AI as a feature, not a moat; value prop doesn't depend on it; easily replicated by a model update or platform entry. |
| 1 | **(hard auto-pass)** No meaningful AI component -- pure software, services, or hardware. ID8's mandate is AI-focused. |

**Subcategory checklist:**

<!-- SUBCATEGORIES: ai_score -->

**Terms (16.7%)** -- bad terms can make a good deal uninvestable, and now
score on the same curve as every other dimension: they drag the weighted
average through the normal 16.7% weight rather than gating the deal outright
(see "Hard auto-pass vs. soft pass" below for what changed from earlier
rubric versions). ID8 does not pay a recurring management fee, ever; a deal
with one still scores 1 here, it just no longer auto-kills the deal by
itself -- it kills it through the weighted average like a confirmed 1 on any
other dimension would.

| Score | Anchor |
| --- | --- |
| 4 | Better than 0/0/10: carry below 10% with pro-rata confirmed, full information rights, clean single-layer SPV or direct co-invest, no upfront fee. |
| 3 | Standard 0/0/10 -- the ID8 baseline: 0% recurring management fee, 0% upfront access fee, 10% carry, reasonable time horizon, some information rights. |
| 2 | Elevated carry (10-15%), no recurring management fee, upfront access fee at or below 2% (the Polymarket standard), limited information rights or multi-layer SPV. |
| 1 | Recurring annual management fee (any amount) -- OR carry >15% with upfront fee >2% -- OR carry >20% regardless of fee. |

Polymarket precedent for the Score 2/3 boundary: ID8 paid ~$14/share upfront
on a $103.66 base (~13.5% deal-level cost) for secondary entry into the
NYSE/ICE-led $600M round, no recurring fee, SPV carry 14-15%. That is the
ceiling -- if carry is at or above 15%, the upfront fee must be at or below
2%. This anchor is the fund's actual live economics (fund-level: 2%
management fee / 20% carry; the LP co-investment vehicle used for one-off
secondary deals like Polymarket: 2% upfront fee, 15% carry, no recurring
management fee).

**Subcategory checklist:**

<!-- SUBCATEGORIES: terms -->

## Diligence Confidence

Separate from the numeric score -- report one of these, and don't let a
thinly-sourced 3.4 look the same as a well-documented 3.4:

- **HIGH** -- strong internal and external data; score is reliable. Rare for
  this pass, since Stage 1 is web-research-only with no internal deck access.
- **MEDIUM** -- some verified data, some gaps; score is directionally right
  (solid press coverage, Crunchbase/Sacra-style estimates).
- **LOW** -- mostly public info, thin disclosure; score is preliminary. This
  is the expected, *normal* outcome for a private company that doesn't
  publish financials -- it is not itself a strike against the company.

## Hard auto-pass vs. soft pass

Not every subcategory 1 is a deal-killer. Terms no longer has a hard
auto-pass trigger of its own -- as of v4 it is a fully normal weighted
dimension, so a bad-terms deal drags the average through its 16.7% weight
like a confirmed weak score anywhere else, rather than ending the deal
outright the way it used to.

**Hard auto-pass -- deal is over, regardless of the weighted average:**
- No AI component
- No credible access path (Score 1 on Lead / Round Dynamics)
- Founder red flags -- verified negative history
- Confirmed (not undisclosed) weak fundamentals or sub-2x return potential

**Soft pass -- continues with caveats, does not kill the deal:**
- Revenue/NDR/burn/LTV:CAC not publicly disclosed
- Founder background unverified
- Non-Tier-1 VC lead at Series B+
- Elevated or bad Terms (recurring fee, high carry) -- previously a hard
  auto-pass, now a soft drag through the weighted average like everything
  else

## Pipeline calibration reference

Real ID8 deal history, for calibration. FQ = Founder/Team Quality, not
backfilled for pre-v2.1 deals (shown as --). Polymarket's LD is `3*`
(Domain-Strategic path, NYSE/ICE lead). The Wtd Avg column is carried over
unchanged from the prior rubric versions that scored these deals -- v3.1's
20/20/20/20/20/gate weighting (Terms gate-only), itself carried over from
v2.1's 20/20/20/20/15/5 weighting before that. v4 moves Terms from gate-only
into the same equal-weight pool as everything else (16.7% × 6) and derives
each dimension score from its fixed subcategories rather than a holistic
call -- use the per-dimension scores here only to calibrate your own anchor
judgment; don't expect this version's math on these same per-dimension scores
to reproduce this exact historical average.

| Company | Status | LD | AI | FQ | Fund. | Ret. | Terms | Wtd Avg | Stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Saronic | Invested | 4 | 4 | 4 | 4 | 4 | 3 | 3.8 | D |
| Micro1 | Active | 4 | 4 | -- | 4 | 4 | 3 | 3.8 | B |
| PermitFlow | Timing | 4 | 4 | -- | 4 | 3 | 3 | 3.7 | B |
| ElevenLabs | Active | 3 | 4 | -- | 4 | 4 | 2 | 3.4 | C |
| Deepgram | Active | 3 | 4 | -- | 4 | 4 | 2 | 3.4 | C |
| Polymarket | Invested | 3* | 4 | 4 | 3 | 4 | 2 | 3.3 | C |
| Kalshi | Active | 2 | 2 | -- | 4 | 3 | 2 | 2.6 | B |
| Airwallex | Passed | 4 | 2.5 | -- | 4 | 3 | 0 | 2.9 | D |
| Mind Robotics | Watch List | 2 | 4 | -- | 2 | 3 | 2 | 2.7 | A |
| Hayden AI | Passed | 1 | 4 | -- | 3 | 3 | 3 | -- | B |
| Erebor | Passed | 2.5 | 1 | -- | 1 | 2 | 3 | -- | B |

Hayden AI and Erebor show -- for weighted average: they triggered a hard
auto-pass (Score 1 on Lead/Round Dynamics and AI Score respectively) before
the average became relevant.

Be skeptical throughout. No evidence found for a subcategory means the
data-missing anchor (usually 2), not a guess in either direction. Never
fabricate a metric or a source.
