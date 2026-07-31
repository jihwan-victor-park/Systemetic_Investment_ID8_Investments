# Radar Heat Score: Confidence, Data Coverage, and a Worked Example

> **Status:** guideline, built on top of the already-shipped Radar hazard
> model ([RADAR_SIGNAL_ENGINE.md](RADAR_SIGNAL_ENGINE.md),
> [RADAR_PLAN.md](RADAR_PLAN.md)) -- this doc adds nothing to the timing
> math itself. It (1) reconciles the `Heat_Score_Signal_Framework.xlsx`
> signal list Oscar shared with Isabella against what's actually built, (2)
> states Isabella's 2026-07-30 mandate as four explicit rules with their
> code locations, and (3) gives a reproducible, traceable worked example.
> **Written:** 2026-07-30

---

## 1. Reconciling the spreadsheet with the shipped model

The uploaded `Heat_Score_Signal_Framework.xlsx` lays out 13 signals across 5
categories, each with a source and a 0-10 scoring guidance, weighted to sum
to 100 -- a classic weighted-average scorecard. That is **not** the model
this codebase runs. RADAR_SIGNAL_ENGINE.md §4 made that call explicitly,
before this guideline existed:

> "A 0-100 heat score is the wrong object. It isn't falsifiable, can't be
> calibrated, and doesn't answer the question asked."

Instead, `deal_intelligence/radar_hazard.py` computes a **hazard**:
`P(raise within 90/180 days)`, from a capital-clock baseline multiplied by
per-signal kernels that rise and fade with the signal's own age (§4.1). The
0-100 "heatPoints" number the hub displays is P180 rescaled for legibility
(`radar_hazard.heat_points()`) -- display sugar, not the model's real unit.

This matters directly for Isabella's mandate: **a weighted-average
scorecard is exactly the design that penalizes missing sources**, because
every signal needs *some* number to feed the sum, and "no data" quietly
becomes "0 out of 10" unless every single row is hand-guarded against it.
The hazard model doesn't have that failure mode by construction -- a signal
with no active kernel simply isn't a term in the product
(`combine_multipliers`, Πᵢ over *active* signals only). That's the
architectural reason this guideline can make strong promises about
"missing ≠ zero" instead of just patching over the spreadsheet's rows.

### 1.1 Where each of the 13 signals actually lives today

| # | xlsx signal | Weight | Status in this codebase |
|---|---|---|---|
| 1 | Latest Round | 0 | Intake field (`roundDate`/`roundSize`, not Apollo) -- `capital_clock.py`'s baseline input |
| 2 | Estimated Time Between Rounds | 0 | `capital_clock.CADENCE_MONTHS_BY_GROWTH` -- research-grounded, not hand-estimated per company |
| 3 | Raise Probability (High/Med/Low → 10/5/0) | 25 | **Superseded wholesale.** This is exactly what `radar_hazard.compute()`'s continuous p90/p180 replaces -- a 3-bucket score can't be calibrated (RADAR_SIGNAL_ENGINE.md §9); a probability can |
| 4 | Industry Growth (Google Trends) | 10 | Not built -- no sensor |
| 5 | MoM Employee Growth (Apollo) | 5 | `radar_signal_series.growth_rate()` → `headcount_growth_40`/`headcount_decline_10` kernels (F2) |
| 6 | Crunchbase Growth Score | 5 | Not built |
| 7 | Step-Up (valuation vs. prior round) | 5 | Not built -- no valuation-step tracking yet |
| 8 | YoY Revenue/ARR Growth (Sacra) | 5 | `radar_timing_signals.extract_growth_tier()`, reading the Stage 1 screen's own research (which may itself cite Sacra/Crunchbase/press) → `hypergrowth_revenue`/`strong_revenue_growth` kernels (F3) -- **this is the signal Isabella's example is about; see §3** |
| 9 | News Volume (Apollo & Sacra) | 10 | Not built as a discrete metric -- press mentions may surface in Stage 1 evidence text, uncounted |
| 10 | Monthly Website Visits Growth | 10 | Not built |
| 11 | Google Trends search interest | 10 | Not built |
| 12 | Crunchbase Heat Score | 10 | Not built -- and wouldn't be adopted as-is even if it were (see §4's rejection of importing another vendor's composite score as an input rather than a raw signal) |
| 13 | Crunchbase Surge Score | 5 | Not built |

Five of thirteen have a real analogue; the rest are candidate sensors, not
gaps in this guideline's scope -- RADAR_SIGNAL_ENGINE.md §10 already tracks
what's built vs. not (filings/F5, social/F3-broad) and this table doesn't
change that roadmap. What it does establish: **signal #8, Sacra-sourced
growth, is precisely the one Isabella's email names**, and it is already
wired through the "missing ≠ zero" discipline (§2) before this guideline's
own additions (§3) on top of it.

---

## 2. What was already true before this change

Worth stating plainly, because Isabella's mandate could be misread as
"go audit the whole pipeline for a bug" -- three of her four asks were
**already invariants** of the hazard architecture, not new work:

1. **"Don't penalize absence from Sacra or a coverage database."**
   `radar_timing_signals.extract_growth_tier()` returns `growthTier = None`
   (not a negative signal) when no growth figure is found in the screen
   text -- "absence of a public number is the normal state for a private
   company" (that module's own docstring). `capital_clock.compute()`
   returns `estMonthlyBurn`/`runwayMonths` as `None`, never `0`, when
   headcount/roundSize/roundDate is missing.
2. **"Treat unavailable data as missing, not zero."** Same evidence as
   above, plus `radar_hazard.baseline_hazard(None)` uses the stated
   population base rate (0.20) rather than 0 for a company with no clock
   reading yet.
3. **"Recalculate the score using only available signals."**
   `combine_multipliers()` is a product over **active** signals only --
   there is no placeholder term for a signal nobody detected. This is true
   by construction, not by a special case guarding against it.

What was genuinely missing, and what this change adds, is **#4 and #5**:
a minimum data-coverage floor, and a way to *see* coverage and confidence
next to the score at all. That's the actual gap this guideline closes.

---

## 3. What this change adds

### 3.1 `dataCoverage` (`deal_intelligence/radar_hazard.py`)

Three sources this pipeline can currently check per company
(`radar_hazard.DATA_SOURCES`):

| Source | True when | False when |
|---|---|---|
| `capitalClock` | headcount, roundSize, and roundDate are all on file | any of the three is missing (no Apollo lookup yet, no intake data) |
| `jobSignals` | an ATS was detected and queried for this company | no ATS could be found -- the job-board sensor never ran |
| `screen` | a Stage 1 screen exists at all | no research pass has run yet -- **this is the "absent from Sacra" case**: the screen is where Sacra/Crunchbase-style growth research would show up, so no screen means that whole channel is unchecked, not "checked and found nothing" |

Filings (F5) and the broader F3 sensors (social, web-diff, community,
reviews) are excluded from the denominator on purpose: they're unbuilt for
**every** company, so including them would lower everyone's coverage
number uniformly without distinguishing any company from any other --
dataCoverage is meant to answer "how much do we know about *this* company
relative to what we could know," not "how much of the roadmap is finished."

`data_coverage()` returns `{coverage: 0-1, available: [...], missing:
[...]}`. `radar_hazard.compute()` now emits `dataCoverage`,
`dataSourcesAvailable`, and `dataSourcesMissing` alongside `heatPoints` --
**and none of them touch heatPoints itself.** Coverage is reported, never
used to suppress or discount the score (see §2's already-true invariant
#3) -- the fix for "missing data shouldn't be punished" is not "also
punish it via a different number."

### 3.2 Confidence is capped by coverage, not the score

`confidence_level()` gains a `coverage` parameter (default `1.0`, so every
pre-existing caller is unaffected). Below `MIN_DATA_COVERAGE` (0.34, i.e.
fewer than 2 of the 3 sources checked), confidence is forced to `"low"`
regardless of how many signal families are active or how fresh they are.

The reasoning, stated once here: a company with one lucky, fresh, active
family but two completely unchecked sources is not "well observed" -- it's
under-observed with a good headline. Reporting that as "medium" or "high"
confidence would reward data availability over the momentum the model is
actually supposed to measure, which is the exact inversion Isabella flagged
("the model will systematically favor companies with strong public-data
coverage rather than companies with actual momentum"). The threshold is a
hand-set prior, same convention as every number in `SIGNAL_KERNELS` --
stated explicitly so it's correctable, not calibrated yet. 1-of-3 (0.333)
sits just below the floor and 2-of-3 (0.667) sits above it; in practice
this means **at least two of the three wired sources must be checked**
before confidence can rise past "low" on the family/freshness heuristic
that already existed.

### 3.3 Display: Heat Score, Confidence, Data coverage together

`hub-next/src/components/radarTableColumns.jsx`'s Heat column tooltip
(the persisted-hazard path) now leads with exactly the three numbers
Isabella's example asked for, in that order:

```
Heat Score 65 · Confidence Medium · Data coverage 67% · P180 65% · P90 41%
· families F2 · access institutional (hot needs 80+ AND syndicate access)
```

matching:

```
Heat Score: 81
Confidence: Medium
Data coverage: 68%
```

A company scanned before this change has no `dataCoverage` field at all --
the tooltip omits that clause rather than showing "0%", since an
unmeasured company isn't the same as a zero-coverage one.

---

## 4. Worked example (reproducible)

`scripts/radar_worked_example.py` runs the **real** pure functions
(`radar_mandate`, `capital_clock`, `radar_timing_signals`, `radar_hazard`,
`radar_state`) end to end, with real dates -- nothing below is hand-typed
to a desired answer. Run it yourself:

```
python3 scripts/radar_worked_example.py
```

### Part 1 -- Northwind Systems, RADAR_PLAN.md §7.1's own company, scan-by-scan

Same company, same round ($32M Series B, closed 2026-02-10), same
headcount ledger and hiring timeline that doc narrates by hand (Director
of Finance first seen 2026-09-14, VP Sales first seen 2026-10-03, both
later filled, Head of Corp Dev posted 2026-12-17) -- run through today's
actual code instead of narrated:

```
scan                                             p90   p180   heat     conf  coverage  families
Scan 1                                         40.6%  64.6%   64.7   medium     66.7%  F2
Scan 2                                         40.6%  64.6%   64.7   medium     66.7%  F2
Scan 3                                         41.7%  66.0%   66.0   medium     66.7%  F2
Scan 4                                         50.0%  75.0%   75.0   medium     66.7%  F2
Scan 5 (finance role filled, VP Sales role filled)  27.8%  47.8%   47.8      low     66.7%  none
Scan 6                                         40.6%  64.6%   64.7   medium     66.7%  F2
```

Two things worth calling out plainly rather than glossing over:

- **The exact figures don't match RADAR_PLAN.md's hand-narrated table**
  (18% → 61% p180 across six scans). That's expected: the doc predates the
  F3 growth-tier kernels and confidence-discount variants shipped
  2026-07-29. The *shape* of the story survives (heat rises as hiring
  signals age toward their kernel peaks); the literal numbers don't, and
  claiming otherwise would be dishonest.
- **Scan 5 drops to `confidence: low, families: none`** the moment both
  open roles get filled -- `radar_state._active_signals` has nothing left
  to report for a *filled* role (its signal disappears entirely rather
  than aging out gracefully). That's a real, existing property of the
  current model worth flagging for Isabella/Oscar, not something this
  change introduces or silently patches.
- **`dataCoverage` sits at 67% for all six scans** -- this trace never
  wires a Stage 1 screen for Northwind, so `screen` stays correctly
  reported as missing throughout, never folded into the timing math.

### Part 2 -- Isabella's mandate, demonstrated directly

Four otherwise-identical snapshots of the same company, differing only in
what a Stage 1 screen (the Sacra-citing research channel) found:

```
scenario                                                     heat     conf  coverage  growthTier
No Stage 1 screen at all (absent from research entirely)     47.8      low     66.7%  None
Screen ran, found nothing quantitative                       47.8      low    100.0%  None
Screen ran, 25x ARR claim, UNVERIFIED (low confidence)        64.5   medium    100.0%  hypergrowth
Screen ran, 25x ARR claim, VERIFIED (high confidence)         85.6   medium    100.0%  hypergrowth
```

What this proves, asserted by the script itself (it exits non-zero if any
of these break):

1. **"No screen" and "screen found nothing" score identically on
   heatPoints** (47.8 both) -- absence of data is never read as a worse
   company than absence of information.
2. **...but `dataCoverage` tells them apart** (67% vs. 100%) -- a partner
   can see *which kind* of quiet a company is, instead of one number
   hiding both.
3. **The unverified 25x-ARR read scores lower than the verified one**,
   same underlying claim, same evidence text -- "recalculate using only
   available signals" cuts both ways: an unconfirmed signal contributes
   *less*, not zero and not full strength.

---

## 5. Open items for Oscar/Isabella sign-off

Stated explicitly, same culture as every other hand-set prior in this
codebase -- correctable, not final:

1. **`MIN_DATA_COVERAGE = 0.34`** (effectively "need 2 of 3 sources"
   before confidence can exceed "low"). Reasonable first cut, not
   calibrated against anything yet.
2. **The 3-source denominator** (`capitalClock`, `jobSignals`, `screen`)
   will need a 4th slot (`filings`) once Clock 1 (RADAR_SIGNAL_ENGINE.md
   §6) is built -- and MIN_DATA_COVERAGE should probably move with it
   rather than staying a fixed fraction of a growing denominator.
3. **The filled-role signal gap** surfaced in Part 1's Scan 5 (a role
   going from open to filled drops its signal entirely rather than
   decaying it) predates this change but is now visible in a way it wasn't
   before -- worth a decision on whether a filled senior hire should carry
   some residual weight for a few months.

---

## 6. Where the code lives

| Concern | File |
|---|---|
| Data coverage + confidence cap | `deal_intelligence/radar_hazard.py` (`data_coverage`, `confidence_level`, `compute`) |
| Wiring per-company source availability | `deal_intelligence/radar_state.py` (`compute_radar_state`'s `job_sensor_available` param, `recompute_and_write`) |
| Tests | `deal_intelligence/tests/test_radar_hazard.py`, `deal_intelligence/tests/test_radar_state.py` (search "Isabella, 2026-07-30") |
| Hub display | `hub-next/src/components/radarTableColumns.jsx` |
| Worked example | `scripts/radar_worked_example.py` |
