<!-- The real ID8 rubric (v3.1, July 2026). Injected verbatim into the stage-1
prompt. Keep the parameter keys in sync with PARAMS in rubric.py. -->

# ID8 Deal Fit Rubric (v3.1)

Score each of the six dimensions below from 1 to 4 using the anchors given.
Five are weighted at exact parity; one (Terms) is gate-only. Report both:

- **Raw average** — plain mean of the five *scored* 1-4 dimensions (Lead /
  Round Dynamics, Founder / Team Quality, Fundamentals, Return Potential, AI
  Score). Terms is never part of this average.
- **Weighted average** — the rubric's actual verdict; this is what gates a
  deal to deep research (see stage1_fit.md's thresholds). Same five
  dimensions, each at exactly 20%, so weighted and raw average happen to be
  the same computation at this rubric version — reported separately because
  the underlying math (and the field names downstream) treat them as
  distinct, and because a future reweighting should not require a schema
  change.

Terms still requires a real, evidence-backed 1-4 score — it drives
hard-auto-pass detection and appears in the one-pager's six-row scoring
table — but it does not contribute to either average above. It is a
pass/fail gate, not graded on a curve. Do not inflate it to try to move the
weighted average; it structurally can't, and evidence padding just makes the
record less useful.

| Dimension | Weight | What It Measures |
| --- | --- | --- |
| **Lead / Round Dynamics** | 20% | GP tier, new vs. re-up (verified), source-VC structural constraint, domain-strategic signal, direct access |
| **Founder / Team Quality** | 20% | Track record, domain authority, execution history, integrity |
| **Fundamentals** | 20% | Revenue, growth, NDR, burn, capital efficiency, moat strength |
| **Return Potential** | 20% | Realistic MOIC and IRR trajectory, secondary-market demand corroboration — no valuation caps |
| **AI Score** | 20% | Depth of AI moat: pure-play vs. data advantage vs. feature wrapper. No meaningful AI component is still a hard auto-pass; otherwise scored on the same curve as everything else. |
| **Terms** | Gate only | Carry, upfront fee, structure. Bad terms are a hard auto-pass trigger; otherwise not weighted. |

## Missing data is not the same as bad data

A score of 1 must mean the anchor is *confirmed* true — not "we couldn't find
a number." Several anchors below are written specifically so that missing or
undisclosed data lands on a 2, not a 1:

- Revenue, NDR, burn, or LTV/CAC not publicly disclosed → work the research
  harder before conceding the gap. First, search press/funding coverage and
  Crunchbase/PitchBook-style estimates thoroughly. Second, check founder/exec
  podcast appearances, conference talks, and interviews for informally-stated
  metrics. Third, if a real number still isn't findable, triangulate an
  `[ESTIMATED]` range: carry forward the revenue multiple implied by a prior
  disclosed round (revenue at that round's valuation) to the current
  valuation, cross-checked against a second estimate from comp-set revenue
  multiples applied to the current valuation. Report both when they diverge
  rather than forcing one number. An `[ESTIMATED]` figure scores 2, 3, or 4 on
  its own merits — never 1, a 1 is reserved for a *confirmed* bad number —
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
- Founder background unverifiable (thin press, no LinkedIn signal) →
  **Founder / Team Quality: 2 max**, flag `[unverified]`.
- Non-Tier-1 lead at Series B+ → **Lead / Round Dynamics: 2** — a real, known
  signal (not missing data), but deliberately anchored at 2 rather than 1 so
  it drags the weighted average via its 20% weight rather than killing the
  deal outright.

Score 1 is reserved for a *confirmed* disqualifying fact. When a dimension
lands on a genuine 1, say in the evidence whether it is one of the hard
auto-pass triggers below.

## Dimension anchors

**Lead / Round Dynamics (20%)** — the primary first-filter signal. A Tier 1+
fund leading with new money at Series B+ is what brings a deal into the ID8
funnel; everything else is evaluation on top of that signal. Always note
`NEW` (first time on the cap table) or `RE-UP` (existing investor increasing
position).

| Score | Anchor |
| --- | --- |
| 4 | New-money lead from a Tier 1+ firm, primary, Series B+. Direct co-invest access confirmed. The cleanest signal ID8 acts on. |
| 3 | Two paths: a Tier 1 VC re-upping with strong conviction at Series B+ with direct access, OR a Domain-Strategic institutional lead (see below) — mark this path `3*`. |
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
Ventures · Greenoaks Capital · DST Global. Under internal revisit — treat as
Tier 1 but flag `[list under revisit]` in the evidence: Spark Capital ·
Greylock · First Round · Firstmark · Greycroft · GV.

*Domain-Strategic leads (Score 3\*):* a large institutional player whose core
business IS the market the company operates in — asymmetric category
knowledge makes their entry a strategic validation signal, not a financial
one. Founding precedent: NYSE/ICE leading Polymarket's $600M round (the
exchange IS the prediction-market venue). Other qualifying patterns: Nvidia
leading an AI infrastructure company, a major bank leading a fintech, a
health system leading a clinical AI company. Generic corporate CVCs and
regional funds do not qualify — there must be genuine domain asymmetry.

**Backtest calibration (ID8 Growth Opportunities Fund I deck, p.14 —
"Quantitatively Validated Systematic Investment Process").** ID8's own
backtest against the broader Series B/C/D universe validates new-money Tier-1
leads specifically — it says nothing about re-up leads:

| Stage | New-money Tier-1 avg MOIC | Full stage universe avg MOIC |
| --- | --- | --- |
| Series B | 14.3x | 6.4x |
| Series C | 7.0x | 4.2x |
| Series D | 7.8x | 3.8x |

Before scoring a re-up lead at the same tier as new money, verify via cap
table history or prior-round disclosures that it is in fact a re-up, not an
assumed one — ID8's own data validates new money specifically, not re-ups
broadly. A re-up claim taken at face value from a press release or company
statement, with no corroborating cap table evidence, should be flagged in the
evidence rather than scored as if confirmed.

**Subcategory checklist** — work through each before committing to the score
above. These are diagnostic, not additively scored: the JSON output still
carries one 1-4 score for this dimension, with the sharpest 2-3 findings from
the list below surfaced in `evidence`, not a checkbox-by-checkbox transcript.

1. **Lead investor tier** — Tier 1+ / Tier 1 / Domain-Strategic / neither, per the tier lists above.
2. **New money vs. re-up — verify, don't assume.** Check cap table history / prior fund stake per the backtest calibration above; do not accept a re-up claim at face value.
3. **Round stage fit vs. mandate.** Series B+ is in-mandate; Series A or earlier is Watch List regardless of score.
4. **Access path quality.** Direct co-invest / single-layer SPV / multi-layer SPV / secondary — and information rights at each.
5. **Domain-strategic signal** (if lead is not a traditional VC). Genuine category asymmetry (NYSE/ICE-Polymarket precedent) vs. generic corporate CVC.
6. **Source VC structural constraint.** Is the source VC providing ID8's access structurally pro-rata-constrained (small fund size relative to check, late fund vintage, concentration-capped) — or opportunistically selling access they could actually afford to keep? Check fund size, vintage, and existing portfolio concentration.
7. **Lead Conviction.** Partner-level skin in the game: is the specific leading GP personally/reputationally committed (partner bio, prior fund performance, personal co-invest), or is this a junior partner's deal at a name-brand fund?
8. **Institutional Momentum.** Are existing Tier-1 investors from prior rounds following on alongside the new lead? Following-on insiders is a distinct, corroborating signal from new-money-lead, not the same fact.
9. **Syndicate breadth and allocation dynamics.** Oversubscription, number of credible co-investors, ID8's actual allocation relative to demand.
10. **Round timing and motivation.** Opportunistic (positive inflection, multiple term sheet options) vs. defensive (runway extension, limited alternatives).

**Founder / Team Quality (20%)** — scores the people independently of
product metrics. If information is limited, land on 2 and flag
`[unverified]` rather than guessing up or down.

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

1. **Prior exit / scaling track record.** Scaled to $100M+ ARR or credible exit; lessons visible in how this company is run.
2. **Domain authority.** Years operating inside this exact market before founding — practitioner, executive, or technical lead.
3. **Founding team complementarity.** Technical / GTM / operational coverage across founders; solo-founder or duplicated-skillset gaps.
4. **Recruiting power / talent magnetism.** LinkedIn headcount growth trend, quality of recent senior hires, retention of early employees.
5. **Existing cap table / advisor quality.** Credibility of prior-round investors and operator-advisors — a proxy layer of diligence ID8 can partially free-ride on.
6. **Founder reputation and public presence.** Press, conference talks, technical writing, open-source contributions — hard to fabricate over time.
7. **Execution cadence / velocity.** Track record of hitting (or missing) previously stated milestones and timelines.
8. **Coachability / founder-market adaptability.** Evidence of real pivots or GTM changes in response to market feedback vs. defensive attachment to the original plan.
9. **Founder financial alignment.** Ownership retained, personal capital at risk, compensation discipline relative to company stage.
10. **Red flag / integrity history — CAN OVERRIDE EVERYTHING ELSE.** Litigation, fraud allegations, regulatory action, verified toxic-culture signals. A confirmed hit here is the Founder/Team Quality hard auto-pass regardless of every other subcategory (see anchor row 1 above).

**Fundamentals (20%)** — moat strength and competitive positioning ·
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
| 2 | Early traction, some positive signals, most metrics below threshold — OR an `[ESTIMATED]` range lands below the $25M/70%-growth bar — OR no real number or usable estimate exists at all (`[NOT PUBLIC]`, last resort). Flag Diligence Confidence LOW when this 2 reflects a data gap with no usable estimate, MEDIUM when it reflects a genuine `[ESTIMATED]` figure. |
| 1 | **(hard auto-pass)** *Confirmed* sub-$5M ARR, sub-40% growth, NDR <100%, LTV/CAC <2x, burn >100% of revenue — not merely undisclosed, and never reached via an `[ESTIMATED]` figure alone. Pre-revenue/pre-commercial companies with nothing to disclose also land here; that is a real gap, not a data-availability one. |

An `[ESTIMATED]` figure can land any of scores 2-4 depending on where it
falls against these anchors — it is never itself a 1, and it caps Diligence
Confidence at MEDIUM (see "Missing data is not the same as bad data" above).

**Subcategory checklist:**

1. **Revenue scale and growth rate.** Absolute ARR and YoY growth — both must be assessed together, not independently.
2. **Net Dollar Retention (NDR).** Expansion vs. flat vs. shrinking — cleanest proxy for real product value after the initial sale.
3. **Gross margin and unit economics.** LTV/CAC, gross margin, contribution margin — is growth value-creating or value-destroying.
4. **Burn rate and runway discipline.** Burn as % of revenue and months of runway at current spend.
5. **Customer concentration risk.** Share of revenue from top 1/5/10 customers — whale-contract risk hiding inside a strong ARR number.
6. **Capital Efficiency / preferred stack structure.** How lean is the liquidation preference stack ahead of this round? A lean preferred stack signals capital discipline and protects downside; a stacked, senior-heavy cap table erodes both.
7. **Competitive moat durability.** Structural (network effects, regulatory barrier, switching costs) vs. narrative-heavy ("great team," "we move fast").
8. **Market size and TAM expansion path.** Is the current market alone venture-scale, and is there a credible, already-in-motion adjacent expansion path.
9. **Valuation vs. comp set.** Revenue multiple at entry vs. public and private comps, growth-adjusted (Rule-of-40-style). Mandatory in every screen; write `[NOT PUBLIC]` if unavailable, never estimate without triangulation and labeling.
10. **Sector disruption risk.** Exposure to foundational-model capability creep, regulatory shifts, or macro cyclicality that could impair the business model within the hold period.

**Return Potential (20%)** — no valuation caps. Score on realistic MOIC/IRR
given entry price, growth rate, dilution, and exit path. Ask what the
company must achieve at this entry price for ID8 to return 6x, and whether
that's the base case or the bull case. Model at least two future rounds of
dilution (~20-25% each) before exit; for secondaries, calculate net IRR
inclusive of any upfront access fee.

| Score | Anchor |
| --- | --- |
| 4 | 6x+ MOIC / 30%+ IRR as the *base* case, not the bull case. Exit path visible, meaningful downside protection. |
| 3 | 3-6x MOIC / 20-30% IRR. Reasonable base case, some execution risk, entry justified but projections require discipline. |
| 2 | 2-3x MOIC / 10-20% IRR. Below venture scale — competition too intense, entry too high, or TAM too narrow to reach 6x in the base case. |
| 1 | **(hard auto-pass)** Below 2x MOIC / below 10% IRR. Meaningful capital-loss risk; does not meet ID8's minimum return threshold. |

**Position-level calibration (deck p.21, as of May 29, 2026).** Live anchor
points for reasoning about realistic MOIC/IRR, not just the abstract
6x/base-case framework:

| Company | MOIC | IRR | Exit / Status | Hold |
| --- | --- | --- | --- | --- |
| Aven | 2.0x | 39.7% | Active | — |
| Base Power | 3.0x | 459.0% | Active | — |
| CoreWeave | 2.6x | 574.5% | IPO | 6 mo |
| Groq | 4.7x | 205.4% | M&A | 17 mo |
| Scale AI | 2.0x | 114.3% | M&A | 11 mo |
| Replit | 3.0x | 364.8% | Active | — |
| Together AI | 2.3x | 99.0% | Active | — |
| Saronic | 1.0x | — | At cost, new | — |
| Polymarket | 1.2-1.3x | 317.6% | Active | — |
| Reflection AI | 1.0x | — | At cost, new | — |

Manager-level blended: 2.2yr average hold, 1.9x MOIC, 158.3% IRR.

**Subcategory checklist:**

1. **Entry valuation vs. growth-adjusted multiple.** Is the entry multiple justified once growth and margin trajectory are factored in, not judged on multiple alone.
2. **Base-case MOIC realism.** What must be true — revenue, margin, exit multiple — for 6x, and is that the base case or the bull case dressed up as one.
3. **Exit path clarity.** IPO readiness, active M&A appetite in the sector, precedent exits of genuinely comparable companies.
4. **Dilution modeling.** Explicitly model at least two future financing rounds (~20-25% each) before exit.
5. **Time to liquidity / IRR sensitivity.** MOIC alone is insufficient — the same MOIC over 4 years vs. 12 years is a fundamentally different IRR outcome.
6. **Downside protection.** Liquidation preference, pro-rata rights, seniority; for secondaries, discount/premium paid vs. last priced round.
7. **Comparable exit multiples.** Anchor exit-multiple assumptions to a genuinely comparable precedent set, not aspirational comps from a different category or cycle peak.
8. **Follow-on capital availability.** Will this company be able to raise its next round at an up-round given current sector/stage investor appetite.
9. **Secondary market demand signal.** Check whether the company appears on the current Setter Capital "Setter 30" (deck p.16 — ID8's quarterly-ranked list of the most sought-after venture-backed companies in the global secondary market; ID8 already has three portfolio companies on it) or is reported as actively traded by Forge, Caplight, EquityZen, or similar secondary marketplaces. This is an external, checkable corroboration of the modeled exit thesis — not a substitute for it.
10. **Portfolio fit / concentration.** Does this deal diversify ID8's book or concentrate it further in an already-heavy thesis, sector, or vintage.

**AI Score (20%)** — does AI constitute the company's actual moat, or is it a
feature layer a foundational-model update could replicate? Test: could this
product become a plugin or default feature of Claude, GPT, or Gemini without
material loss? If yes, it scores 2 or below. Scored and weighted at parity
with the other four dimensions — but its bottom anchor is still a hard
auto-pass, exactly like Lead / Round Dynamics' bottom anchor: a real 1-4
score is required either way, and "no meaningful AI" ends the deal on its own
regardless of how everything else scores.

| Score | Anchor |
| --- | --- |
| 4 | Pure-play AI. Architecture, proprietary data flywheel, or fine-tuned model is defensible and the core moat — cannot be trivially replicated by a model update. |
| 3 | AI-enabled with structural advantage: AI materially drives margin structure, data compounding, customer value prop, or distribution. Includes vertical AI with regulatory/workflow moats (health AI, compliance). |
| 2 | AI-adjacent / feature layer. Uses AI as a feature, not a moat; value prop doesn't depend on it; easily replicated by a model update or platform entry. |
| 1 | **(hard auto-pass)** No meaningful AI component — pure software, services, or hardware. ID8's mandate is AI-focused. |

**Subcategory checklist:**

1. **Architecture ownership.** Proprietary model, fine-tune, or training pipeline vs. a thin wrapper calling a third-party foundation-model API.
2. **Data flywheel.** Does usage generate proprietary data that compounds product quality over time, and is there concrete evidence of it (stated improvement cadence, proprietary datasets, retraining cycle)?
3. **Replicability test.** Could this product become a plugin or default feature of Claude, GPT, or Gemini without material loss? Name what specifically survives that test and what doesn't.
4. **Technical team depth.** Research/ML headcount, published papers or technical blog posts, notable AI hires — vs. a generic engineering team bolting on API calls.
5. **Compute / infra investment.** Evidence of real training or inference infrastructure spend (GPU clusters, model-serving cost structure) vs. a SaaS wrapper with negligible marginal AI cost.
6. **Vertical workflow or regulatory moat.** For vertical AI (health, legal, compliance), does the AI depend on workflow integration or regulatory approval a generic model can't easily replicate?
7. **Independent performance validation.** Any third-party benchmarks, evals, or comparisons validating the model's edge over commodity foundation models.
8. **Margin structure tied to AI.** Does AI materially change unit economics (e.g., automation displacing headcount-driven cost), and is there evidence of that margin shift?
9. **Competitive response risk.** History in this specific product category of feature-layer competitors getting steamrolled by a foundational-model update (OpenAI/Anthropic/Google shipping a similar capability natively).
10. **Narrative vs. reality check.** Does the company's public "AI-powered" messaging match the actual product architecture? Cross-check marketing claims against job postings, technical writing, and engineering talks.

**Terms (Gate only)** — bad terms can make a good deal uninvestable. This
dimension is scored 1-4 for the record and for hard-auto-pass detection, but
does not enter the weighted or raw average — see the note at the top of this
document. ID8 does not pay a recurring management fee, ever — any deal with
one is a hard auto-pass regardless of every other dimension.

| Score | Anchor |
| --- | --- |
| 4 | Better than 0/0/10: carry below 10% with pro-rata confirmed, full information rights, clean single-layer SPV or direct co-invest, no upfront fee. |
| 3 | Standard 0/0/10 — the ID8 baseline: 0% recurring management fee, 0% upfront access fee, 10% carry, reasonable time horizon, some information rights. |
| 2 | Elevated carry (10-15%), no recurring management fee, upfront access fee at or below 2% (the Polymarket standard), limited information rights or multi-layer SPV. |
| 1 | **(hard auto-pass)** Recurring annual management fee (any amount) — OR carry >15% with upfront fee >2% — OR carry >20% regardless of fee. |

Polymarket precedent for the Score 2/3 boundary: ID8 paid ~$14/share upfront
on a $103.66 base (~13.5% deal-level cost) for secondary entry into the
NYSE/ICE-led $600M round, no recurring fee, SPV carry 14-15%. That is the
ceiling — if carry is at or above 15%, the upfront fee must be at or below 2%.
This anchor is the fund's actual live economics (fund-level: 2% management
fee / 20% carry; the LP co-investment vehicle used for one-off secondary
deals like Polymarket: 2% upfront fee, 15% carry, no recurring management
fee), preserved verbatim from v2.1 — only the weighting changed, not the gate
logic.

## Diligence Confidence

Separate from the numeric score — report one of these, and don't let a
thinly-sourced 3.4 look the same as a well-documented 3.4:

- **HIGH** — strong internal and external data; score is reliable. Rare for
  this pass, since Stage 1 is web-research-only with no internal deck access.
- **MEDIUM** — some verified data, some gaps; score is directionally right
  (solid press coverage, Crunchbase/Sacra-style estimates).
- **LOW** — mostly public info, thin disclosure; score is preliminary. This
  is the expected, *normal* outcome for a private company that doesn't
  publish financials — it is not itself a strike against the company.

## Hard auto-pass vs. soft pass

Not every Score 1 is a deal-killer.

**Hard auto-pass — deal is over, regardless of the weighted average:**
- No AI component
- Recurring annual management fee (any amount)
- Carry >15% with upfront fee >2%, or carry >20% regardless of fee
- No credible access path (Score 1 on Lead / Round Dynamics)
- Founder red flags — verified negative history
- Confirmed (not undisclosed) weak fundamentals or sub-2x return potential

**Soft pass — continues with caveats, does not kill the deal:**
- Revenue/NDR/burn/LTV:CAC not publicly disclosed
- Founder background unverified
- Non-Tier-1 VC lead at Series B+

## Pipeline calibration reference

Real ID8 deal history, for calibration. FQ = Founder/Team Quality, not
backfilled for pre-v2.1 deals (shown as —). Polymarket's LD is `3*`
(Domain-Strategic path, NYSE/ICE lead). The Wtd Avg column is carried over
unchanged from the prior rubric versions that scored these deals — v2.1's
20/20/20/20/15/5 weighting, in turn carried over from an earlier 5-dimension
equal-weight rubric (LD/AI/Fundamentals/Return/Terms, all at 20%) before FQ
existed. v3.1's 20/20/20/20/20/gate math brings the rubric back to that same
five-way-equal shape, with FQ now occupying the fifth slot Terms once held
and Terms demoted to gate-only — but use the per-dimension scores here only
to calibrate your own anchor judgment; don't expect this version's math on
these same per-dimension scores to reproduce this exact historical average.

| Company | Status | LD | AI | FQ | Fund. | Ret. | Terms | Wtd Avg | Stage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Saronic | Invested | 4 | 4 | 4 | 4 | 4 | 3 | 3.8 | D |
| Micro1 | Active | 4 | 4 | — | 4 | 4 | 3 | 3.8 | B |
| PermitFlow | Timing | 4 | 4 | — | 4 | 3 | 3 | 3.7 | B |
| ElevenLabs | Active | 3 | 4 | — | 4 | 4 | 2 | 3.4 | C |
| Deepgram | Active | 3 | 4 | — | 4 | 4 | 2 | 3.4 | C |
| Polymarket | Invested | 3* | 4 | 4 | 3 | 4 | 2 | 3.3 | C |
| Kalshi | Active | 2 | 2 | — | 4 | 3 | 2 | 2.6 | B |
| Airwallex | Passed | 4 | 2.5 | — | 4 | 3 | 0 | 2.9 | D |
| Mind Robotics | Watch List | 2 | 4 | — | 2 | 3 | 2 | 2.7 | A |
| Hayden AI | Passed | 1 | 4 | — | 3 | 3 | 3 | — | B |
| Erebor | Passed | 2.5 | 1 | — | 1 | 2 | 3 | — | B |

Hayden AI and Erebor show — for weighted average: they triggered a hard
auto-pass (Score 1 on Lead/Round Dynamics and AI Score respectively) before
the average became relevant.

Be skeptical throughout. No evidence found for a dimension means the
data-missing anchor (usually 2), not a guess in either direction. Never
fabricate a metric or a source.
