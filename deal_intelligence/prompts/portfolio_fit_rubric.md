<!-- The Portfolio Fit rubric (v1, July 2026) -- the lighter-than-Stage-1 pass
over partner VC portfolio companies (no live round, no entry price). Injected
via rubric_portfolio.rubric_text(), which splices each dimension's anchor
table into its <!-- ANCHORS: <key> --> marker below, generated from PARAMS in
rubric_portfolio.py -- that file is the single source of truth for dimension
keys, labels, and anchor text. Keep dimension keys in sync with PARAMS. -->

# ID8 Portfolio Fit Rubric (v1)

Score each of the four dimensions below from 1 to 4. All four sit at **exact
parity, 25% each**. This is a deliberately shallower instrument than the six-
dimension Stage 1 rubric (`prompts/rubric.md`) -- it exists to monitor a
partner VC's portfolio company that has no live round, not to screen an
active deal.

## Why this isn't Stage 1 with fewer dimensions bolted on

Two of Stage 1's six dimensions don't transfer at all: **Lead / Round
Dynamics** (lead tier, new-vs-re-up, timing/motivation) presupposes an actual
round in motion, which a portfolio company sitting quietly in a cap table
does not have. **Terms** (carry, upfront fee, structure) presupposes ID8 is
actually being offered access to a deal -- there is no deal yet. **Return
Potential**'s MOIC/IRR framing also doesn't transfer, since there is no ID8
entry price to compute a multiple from; what does transfer from it is the
underlying "is this plausibly a venture-scale outcome" judgment, folded into
Fundamentals & Scale Ceiling below.

| Dimension | Weight | What It Measures |
| --- | --- | --- |
| **AI / Thesis Fit** | 25% | Depth of the AI moat -- pure-play vs. data advantage vs. feature wrapper. No meaningful AI component is still a hard auto-pass, identical to Stage 1. |
| **Founder / Team Quality** | 25% | Track record, domain authority, execution history, integrity -- one holistic call, not itemized subcategories. |
| **Fundamentals & Scale Ceiling** | 25% | Revenue/growth signal where available, moat durability, and whether the business could plausibly become a $1B+ outcome -- not what ID8's return would be at an entry price that doesn't exist yet. |
| **Stage & Backing Quality** | 25% | Round stage and the quality of investors already on the cap table. Replaces Lead/Round Dynamics' subcategories that don't require a live round. |

## Holistic scoring, not itemized subcategories

Stage 1 breaks every dimension into 2-10 fixed subcategories, each scored and
evidenced independently. This rubric does not -- that's the actual "lighter"
lever, not a shorter research pass. Score each dimension **once**, holistically,
against the anchor table below it, and support it with **one sentence of
evidence** (<= 25 words). This is what keeps the per-company cost and output
size small enough to run over thousands of rows; the model still has to reason
over the same underlying facts, it just doesn't write a graded sub-answer for
each one.

## Missing data is not the same as bad data

Same principle as Stage 1: a score of 1 means the anchor's bad case is
*confirmed*, not that data is merely unavailable. Most portfolio rows arrive
with only a name, industry, and round history from PitchBook's investment-list
data -- richer detail (description, category, financing recency, headcount)
depends on whether that specific company has been through the deeper
enrichment pass yet. Undisclosed or thin data lands on that dimension's
own data-missing anchor (usually 2), never a 1.

## AI / Thesis Fit

<!-- ANCHORS: ai_thesis_fit -->

## Founder / Team Quality

<!-- ANCHORS: founder_team_quality -->

## Fundamentals & Scale Ceiling

<!-- ANCHORS: fundamentals_scale_ceiling -->

## Stage & Backing Quality

<!-- ANCHORS: stage_backing_quality -->

## Hard auto-pass vs. soft pass

Identical mechanism to Stage 1: the model reports `hard_auto_pass` explicitly
as a boolean plus a reason, rather than code inferring it from a raw score, so
a single harsh dimension can't silently kill an otherwise strong company.

**Confirmed hard-pass conditions** (any one triggers `hard_auto_pass: true`):
- No meaningful AI component -- a thin wrapper around a third-party
  foundation-model API with no differentiation, confirmed from the company's
  own description/product, not merely a thin PitchBook category label.
- Verified founder red flags -- confirmed litigation, fraud allegations,
  regulatory action, or toxic-culture reporting.
- Confirmed business failure -- the company is shut down, an acqui-hire with
  no surviving product, or otherwise confirmed dead (distinct from the
  deterministic `businessStatus` exclusion applied upstream, which only
  catches PitchBook's own "Out of Business"/"Acquired"/"IPO" field; this
  catches what a real search surfaces that PitchBook's field hasn't caught
  up to yet).

**Soft-pass conditions** (drag the relevant dimension's score, never force a
hard fail):
- Fundamentals genuinely undisclosed and no usable triangulation exists.
- Founder background genuinely unverifiable after a real search effort.
- Backing quality unclear -- no confirmed Tier 1/Tier 1+ investor either way.

Geography (NA/Europe) is **not** scored here at all -- `hqLocation` is
already structured PitchBook data, applied as a deterministic pre-filter
before any company reaches this prompt (see rubric_portfolio.py's docstring).
Spending a research call to re-derive a fact already sitting in a database
field would be pure waste at this scale.

## Stage override: too_early, not a fail

A company below Series B does not hard-fail here -- it is scored for real
(genuine per-dimension evidence, not shortcut to all-1s) and separately
tagged `too_early: true`. This mirrors Stage 1's `watch_list` mechanism:
the point is to bench a strong early-stage company for when it matures into
mandate, not to throw away the signal.

## Decision tiers

Renamed from Stage 1's vocabulary since nothing here gates to deep research
-- it gates to a monitored watchlist inside the Hub:

- `track_priority` -- weighted score >= 3.5
- `track` -- weighted score >= 3.0
- `monitor` -- weighted score >= 2.5
- `drop` -- weighted score < 2.5, or any `hard_auto_pass`
- `too_early` -- stage override fired; real score kept, tier reported
  separately from the score-based bands above

## Probability of next round (3-month band)

Reported in the same JSON response as the fit score above -- one combined
call, not two. Two layers:

1. **Deterministic base rate** (computed in code and supplied to you inline
   further down in this prompt -- not something to derive yourself from
   scratch): months since the company's last recorded financing, compared against
   typical stage cadence (roughly 18-24 months between rounds pre-Series-C,
   24-30 months at Series C/D+). A company well past its stage-typical
   cadence carries a higher base rate; one that just closed a round carries a
   low one.
2. **Qualitative overlay** (your one paid research pass, same call as the fit
   score above): nudge the base rate up or down using whatever your research
   surfaces -- hiring surge (especially GTM/sales roles), a new CFO or Head of
   Corporate Development hire, press reporting the company is "in talks to
   raise," or conversely layoffs/shutdown signal pointing the other way.

Report a **band**, not a fake-precise percentage -- the underlying signal
doesn't support that precision:

- `low` (< 15%)
- `medium` (15-35%)
- `high` (35-60%)
- `imminent` (> 60%)

Support the band with one sentence (<= 25 words) naming whatever moved it off
the deterministic baseline -- or say plainly that nothing did, if your
research surfaced no qualitative signal either way.

Be skeptical throughout, same standard as Stage 1: no evidence for a
dimension means its own data-missing anchor (usually 2), not a guess in
either direction. Never fabricate a fact, a financing date, or a source.
