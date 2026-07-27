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

1. **Lead tier**

| Score | Anchor |
| --- | --- |
| 1 | No credible institutional lead -- insider bridge, anonymous SPV, or a CVC/regional fund with no strategic relevance. |
| 2 | Non-Tier-1 VC leading the round. |
| 3 | Tier 1 VC (per the Tier 1 list) or a qualifying Domain-Strategic lead -- genuine category asymmetry, not a generic corporate CVC. |
| 4 | Tier 1+ VC (per the Tier 1+ list) leading the round. |

2. **New vs re-up**

| Score | Anchor |
| --- | --- |
| 1 | Re-up claim taken at face value with no cap-table or prior-round corroboration -- unverifiable, treated as unconfirmed. |
| 2 | Confirmed re-up -- an existing investor increasing its position, not new money. |
| 3 | Re-up verified via cap table/prior-round disclosure, from a Tier 1+ firm, with strong stated conviction. |
| 4 | Verified new money -- the lead is on the cap table for the first time, ID8's strongest backtested predictor of returns. |

3. **Stage fit**

| Score | Anchor |
| --- | --- |
| 1 | Pre-seed or Seed -- well outside mandate, no near-term path to Series B+. |
| 2 | Series A -- out of mandate for now but on a plausible path to Series B; file to Watch List. |
| 3 | Series B/C/D but the round has mixed characteristics (bridge-to-B, extension round) vs. a clean primary. |
| 4 | Clean primary round at Series B, C, or D -- squarely in mandate. |

4. **Domain-strategic**

| Score | Anchor |
| --- | --- |
| 1 | Lead claims domain relevance but is a generic corporate CVC or regional fund with no genuine category asymmetry. |
| 2 | Lead is a traditional financial VC -- domain-strategic signal not applicable to this deal. |
| 3 | Lead has adjacent domain relevance but the asymmetry is partial (e.g. a fintech-adjacent bank, not a direct incumbent). |
| 4 | Lead is a large institutional player whose core business IS the company's market (NYSE/ICE-Polymarket precedent) -- genuine, direct asymmetry. |

5. **Lead conviction**

| Score | Anchor |
| --- | --- |
| 1 | Deal sourced/led by a junior associate or scout check with no partner-level sponsorship visible. |
| 2 | A named partner is involved but with no visible personal track record or reputational stake disclosed. |
| 3 | The leading GP has a credible prior-fund track record and is the named partner driving the deal. |
| 4 | The leading GP is personally/reputationally committed -- strong prior-fund performance, personal co-invest, or a bio establishing direct conviction. |

6. **Institutional momentum**

| Score | Anchor |
| --- | --- |
| 1 | Existing investors from prior rounds are confirmed NOT participating -- a negative signal, insiders passing. |
| 2 | No visible signal either way on prior-round investor participation in this round. |
| 3 | Some prior-round investors are following on, but participation is partial or unconfirmed beyond a press mention. |
| 4 | Existing Tier-1 investors from prior rounds are confirmed following on alongside the new lead -- a distinct, corroborating signal. |

7. **Existing Tier 1**

| Score | Anchor |
| --- | --- |
| 1 | No Tier 1 or Tier 1+ investors anywhere on the pre-round cap table. |
| 2 | Cap table history is unclear/unverifiable, or only lower-tier/angel investors are confirmed. |
| 3 | At least one Tier 1 firm is confirmed on the pre-round cap table. |
| 4 | Multiple Tier 1/Tier 1+ firms are confirmed on the pre-round cap table -- a strong pre-existing pedigree signal. |

8. **Timing/motivation**

| Score | Anchor |
| --- | --- |
| 1 | Defensive raise -- runway extension, down-round pressure, or limited alternatives visible. |
| 2 | Motivation is unclear or undisclosed; no evidence either of opportunistic strength or defensive need. |
| 3 | Opportunistic raise with at least one credible alternative term sheet or investor reported. |
| 4 | Clearly opportunistic -- positive inflection point, multiple credible term sheet options, company controlling the process. |

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

1. **Prior exit**

| Score | Anchor |
| --- | --- |
| 1 | First-time founder(s) with no prior scaling or exit track record at all. |
| 2 | Some operating experience but nothing scaled meaningfully (no $100M+ ARR company, no exit). |
| 3 | First-time founder with elite pedigree (FAANG, top-tier academic, relevant domain leadership) but no exit yet. |
| 4 | Serial founder with a meaningful prior exit or a company scaled to $100M+ ARR. |

2. **Domain authority**

| Score | Anchor |
| --- | --- |
| 1 | No prior experience in this market -- founders are entering a domain they've never operated in. |
| 2 | Adjacent but not direct domain experience (a related market, not this exact one). |
| 3 | Meaningful prior operating time in this exact market, though not in a senior/executive capacity. |
| 4 | Deep domain authority -- years as a practitioner, executive, or technical lead in this exact market before founding. |

3. **Team complement**

| Score | Anchor |
| --- | --- |
| 1 | Solo founder or a founding team with duplicated skillsets and no coverage of a critical function. |
| 2 | Founding team has partial coverage but a visible, material gap (e.g. no technical co-founder for a deep-tech company). |
| 3 | Founding team covers the critical functions with reasonable but not ideal complementarity. |
| 4 | Clean technical/GTM/operational complementarity with no material coverage gap. |

4. **Recruiting power (as in team growth)**

| Score | Anchor |
| --- | --- |
| 1 | Headcount flat or shrinking; visible attrition among early/senior hires. |
| 2 | Headcount growth is slow or unverifiable from LinkedIn/public signal. |
| 3 | Steady headcount growth with some credible senior hires. |
| 4 | Strong LinkedIn headcount growth trend with notable senior hires and retention of early employees. |

5. **Public presence**

| Score | Anchor |
| --- | --- |
| 1 | No public footprint at all for the founders -- cannot assess reputation. |
| 2 | Minimal public presence; thin press, no conference/technical presence found. |
| 3 | Regular press mentions or some conference/technical writing presence. |
| 4 | Strong, consistent public presence -- press, conference talks, technical writing, or open-source contributions hard to fabricate. |

6. **Integrity**

| Score | Anchor |
| --- | --- |
| 1 | Verified negative history -- litigation, fraud allegations, regulatory action, or confirmed toxic-culture signals. |
| 2 | Background is genuinely unverifiable after real search effort -- flag [unverified], a gap, not a red flag. |
| 3 | Background verified with no red flags found, though the search surface was limited. |
| 4 | Background thoroughly verified across multiple independent sources with no red flags found. |

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

1. **Revenue/growth**

| Score | Anchor |
| --- | --- |
| 1 | Confirmed sub-$5M ARR and sub-40% YoY growth -- a real, disclosed weak number, not a data gap. |
| 2 | No disclosed revenue/growth and no usable [ESTIMATED] triangulation exists, or an [ESTIMATED] figure lands below the $25M ARR / 70% growth bar. |
| 3 | $25M+ ARR with >70% YoY growth, confirmed or [ESTIMATED] via triangulation. |
| 4 | $50M+ ARR with 100%+ YoY growth, confirmed or [ESTIMATED] via triangulation. |

2. **NDR**

| Score | Anchor |
| --- | --- |
| 1 | Confirmed NDR below 100% -- shrinking accounts. |
| 2 | NDR not disclosed and no usable estimate exists. |
| 3 | NDR above 110%, confirmed or credibly estimated from comparable-stage peers. |
| 4 | NDR above 130%, confirmed or credibly estimated from comparable-stage peers. |

3. **Margins/unit econ**

| Score | Anchor |
| --- | --- |
| 1 | Confirmed LTV/CAC below 2x -- growth is value-destroying. |
| 2 | Gross margin/unit economics not disclosed and no usable estimate exists. |
| 3 | LTV/CAC above 3x with reasonable gross margin -- growth is value-creating. |
| 4 | LTV/CAC above 5x with strong gross and contribution margin. |

4. **Burn/runway**

| Score | Anchor |
| --- | --- |
| 1 | Confirmed burn above 100% of revenue -- burning faster than it earns with no offsetting signal. |
| 2 | Burn/runway not disclosed and no usable estimate exists. |
| 3 | Burn below 50% of revenue with a credible runway at current spend. |
| 4 | Burn below 20% of revenue -- strong capital discipline relative to revenue. |

5. **Customer concentration**

| Score | Anchor |
| --- | --- |
| 1 | Confirmed whale-contract risk -- a single customer or a small handful account for the clear majority of revenue. |
| 2 | Customer concentration not disclosed and cannot be estimated. |
| 3 | Some concentration in the top customers, but diversified enough that no single loss would be existential. |
| 4 | Broad, diversified customer base with no material single-customer or top-N concentration risk. |

6. **Pref stack**

| Score | Anchor |
| --- | --- |
| 1 | Confirmed stacked, senior-heavy liquidation preference structure ahead of this round. |
| 2 | Cap table/pref stack structure not disclosed and cannot be estimated. |
| 3 | Preferred stack is reasonably lean, with no material senior-preference overhang identified. |
| 4 | Lean preferred stack confirmed -- clean capital structure that protects downside and signals capital discipline. |

7. **Moat durability**

| Score | Anchor |
| --- | --- |
| 1 | Moat is purely narrative ("great team," "we move fast") with no structural defensibility identified. |
| 2 | Some structural elements claimed but not clearly evidenced (e.g. asserted network effects with no usage data). |
| 3 | Real but moderate structural moat -- some combination of switching costs, early network effects, or a regulatory edge. |
| 4 | Strong structural moat -- durable network effects, a genuine regulatory barrier, or high switching costs, clearly evidenced. |

8. **Market/TAM**

| Score | Anchor |
| --- | --- |
| 1 | Current market is not venture-scale and no credible adjacent expansion path exists. |
| 2 | Market size or expansion path is unclear/undisclosed and cannot be credibly estimated. |
| 3 | Current market alone is venture-scale, though the adjacent expansion path is more aspirational than in-motion. |
| 4 | Current market is venture-scale and a credible, already-in-motion adjacent expansion path is evidenced. |

9. **Valuation vs comps**

| Score | Anchor |
| --- | --- |
| 1 | Entry valuation is confirmed materially rich vs. growth-adjusted public/private comps. |
| 2 | No public revenue multiple available and no usable [ESTIMATED]/comp-set triangulation exists -- write [NOT PUBLIC]. |
| 3 | Entry multiple is defensible vs. public/private comps on a growth-adjusted (Rule-of-40-style) basis, confirmed or [ESTIMATED]. |
| 4 | Entry multiple is favorable vs. growth-adjusted comps -- priced at a discount to what the growth/margin profile would justify. |

10. **Sector risk**

| Score | Anchor |
| --- | --- |
| 1 | Confirmed acute disruption risk -- foundational-model capability creep, pending regulatory action, or macro cyclicality that could impair the business within the hold period. |
| 2 | Sector risk is unclear or unassessed from available evidence. |
| 3 | Some sector exposure identified but manageable -- not an acute, near-term threat. |
| 4 | Sector is not at acute disruption risk -- durable position against foundational-model creep, regulatory shifts, and macro cyclicality. |

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

1. **Entry multiple**

| Score | Anchor |
| --- | --- |
| 1 | Entry multiple is not justified even after accounting for growth and margin trajectory. |
| 2 | Entry multiple cannot be assessed -- insufficient data on growth/margin trajectory to judge. |
| 3 | Entry multiple is justified once growth and margin trajectory are factored in, though not favorable. |
| 4 | Entry multiple is well justified -- growth-adjusted pricing is attractive relative to trajectory. |

2. **Base-case MOIC**

| Score | Anchor |
| --- | --- |
| 1 | Below 2x MOIC / below 10% IRR as the realistic base case. |
| 2 | 2-3x MOIC / 10-20% IRR -- below venture scale in the base case. |
| 3 | 3-6x MOIC / 20-30% IRR as a realistic base case, with some execution risk. |
| 4 | 6x+ MOIC / 30%+ IRR as the base case (not the bull case), with a credible path shown. |

3. **Exit path**

| Score | Anchor |
| --- | --- |
| 1 | No credible exit path identified -- no IPO readiness signal, no M&A appetite, no comparable precedent exits. |
| 2 | Exit path is unclear or speculative, with only weak precedent. |
| 3 | A reasonable exit path exists (IPO readiness or active M&A appetite in the sector) with some precedent support. |
| 4 | Clear exit path -- strong IPO readiness or active M&A appetite in the sector, with genuinely comparable precedent exits. |

4. **Dilution**

| Score | Anchor |
| --- | --- |
| 1 | Dilution modeling was not attempted, or the deal isn't viable even under a favorable dilution assumption. |
| 2 | Dilution is modeled loosely or with unsupported assumptions. |
| 3 | At least two future financing rounds (~20-25% each) are explicitly modeled before exit, with a viable resulting MOIC. |
| 4 | Dilution is rigorously modeled across multiple future rounds and the return case holds up well even under conservative assumptions. |

5. **Time to liquidity**

| Score | Anchor |
| --- | --- |
| 1 | Time to liquidity is long with no offsetting IRR -- the modeled MOIC only works over an unrealistically extended hold. |
| 2 | Time to liquidity is unclear or unmodeled. |
| 3 | A reasonable time-to-liquidity estimate exists and the resulting IRR is acceptable, even if not exceptional. |
| 4 | Time to liquidity is modeled explicitly and the resulting IRR is strong -- the same MOIC compressed into a shorter, credible hold. |

6. **Downside protection**

| Score | Anchor |
| --- | --- |
| 1 | No meaningful downside protection -- weak or absent liquidation preference, pro-rata, or seniority; for secondaries, a premium paid vs. last priced round. |
| 2 | Downside protection terms are undisclosed or unclear. |
| 3 | Standard downside protection in place -- reasonable liquidation preference, pro-rata rights, and seniority. |
| 4 | Strong downside protection -- favorable liquidation preference/seniority, or for secondaries, a confirmed discount vs. last priced round. |

7. **Exit multiples**

| Score | Anchor |
| --- | --- |
| 1 | Exit-multiple assumptions rely on aspirational comps from a different category or a cycle peak, not a genuinely comparable precedent set. |
| 2 | No genuinely comparable exit precedent set could be identified. |
| 3 | Exit-multiple assumptions are anchored to a reasonably comparable precedent set. |
| 4 | Exit-multiple assumptions are anchored to a genuinely comparable, well-evidenced precedent set. |

8. **Secondary demand**

| Score | Anchor |
| --- | --- |
| 1 | No secondary market signal found, or the company is reported as actively avoided/discounted in secondary trading. |
| 2 | Secondary market activity/demand could not be assessed from available sources. |
| 3 | Some secondary market interest signal exists but not on a named tracked list (Setter 30) or major marketplace. |
| 4 | Company appears on the Setter Capital "Setter 30" or is reported as actively traded by Forge/Caplight/EquityZen or similar -- external corroboration of the exit thesis. |

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

1. **Ownership of models**

| Score | Anchor |
| --- | --- |
| 1 | No proprietary model or fine-tune of any kind -- a thin wrapper calling a third-party foundation-model API with no differentiation. |
| 2 | Some fine-tuning or prompt/pipeline engineering on top of a third-party model, but no owned architecture. |
| 3 | A meaningfully customized or fine-tuned model with real engineering investment, though not a from-scratch architecture. |
| 4 | Proprietary architecture, training pipeline, or deeply fine-tuned model that is defensible and hard to replicate with a foundation-model update. |

2. **Data flywheel / Recurssion**

| Score | Anchor |
| --- | --- |
| 1 | No evidence usage data feeds back into the product at all. |
| 2 | A plausible data flywheel is claimed but with no concrete evidence (no stated improvement cadence or proprietary dataset). |
| 3 | Some concrete evidence of a data flywheel (a proprietary dataset or a stated retraining cycle), though the compounding effect isn't yet demonstrated. |
| 4 | Strong, evidenced data flywheel -- usage data demonstrably compounds product quality over time via a proprietary dataset and an active retraining cycle. |

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

1. **Just assume they are good (unless there's something public)**

| Score | Anchor |
| --- | --- |
| 1 | Confirmed bad terms -- a recurring annual management fee (any amount), or carry >15% with an upfront fee >2%, or carry >20% regardless of fee. |
| 2 | Some public evidence of elevated but not disqualifying terms -- carry 10-15%, upfront access fee at or below 2% (the Polymarket standard), or limited information rights/multi-layer SPV. |
| 3 | Standard 0/0/10 terms confirmed, or no public evidence either way -- assume standard/good absent any adverse public signal. |
| 4 | Better than standard -- carry below 10% with pro-rata confirmed, full information rights, clean single-layer SPV or direct co-invest, no upfront fee. |

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

