# Running the Radar heat-score research (hand off to a separate chat, Haiku model)

## Oscar's explicit call (2026-08-06): no 3rd-party research APIs

The codebase's own `radar_backfill.py`/`radar_market_signals.py` would do
this via direct Perplexity + Google Trends API calls. **Oscar rejected
that** — he wants the research agent itself doing the web research (its
own search/fetch tools), not proxied through a 3rd-party research API.
This doc is the corrected version of that plan.

Two files are already prepared for this:
- [`deal_intelligence/data/radar-companies-research-input.json`](../deal_intelligence/data/radar-companies-research-input.json)
  — all 61 Radar companies with everything already known (name, website,
  description, HQ/region, round/roundDate/roundSize, investors, Tier 1
  firms on cap table, and a locally-computed `predictedWindowOpen` — that
  last one is pure date math, not a web call, so don't re-research it).
  Each company also lists exactly which signals need fresh web research
  (`signalsNeedingWebResearch`) and which are out of scope
  (`signalsNotResearchable` — Apollo-only data this agent has no access
  to).
- [`docs/RADAR_HEAT_SCORE_RULES.md`](RADAR_HEAT_SCORE_RULES.md) — the
  full 16-signal rubric (weights + exact scoring bands), the aggregation
  math, and the required output JSON shape.

## What the new chat should do

1. Read both files above in full before starting.
2. Research companies in modest batches (e.g. 5–8 per Task/Agent call, a
   couple running at once at most) — **not 5 large parallel batches at
   once**. That exact pattern (5 parallel heavy research agents) is what
   burned through the previous session's rate limit with zero saved
   output. Haiku is cheap, but still pace it — sequential-ish is safer
   than maximally parallel here.
3. For each company: research only the signals listed in
   `signalsNeedingWebResearch`, following `RADAR_HEAT_SCORE_RULES.md`'s
   scoring bands exactly. Cite a source for everything you score. Mark
   anything you can't find real evidence for as `computed: false` — never
   guess.
4. Save results as you go (e.g. one JSON file per batch, or append to a
   running file) so a crash mid-run doesn't lose everything again — don't
   hold all 61 results only in conversation state until the very end.
5. Once all 61 are scored, combine into one file, e.g.
   `deal_intelligence/data/radar-heat-scores-2026-08-06.json`, and report
   back a short summary (how many companies got a `normalizedScore`, the
   range, and which companies came back almost entirely `computed:false`
   so Oscar knows where public data just doesn't exist).

Writing the results back into Firestore is a separate, later step —
this pass is research + scoring only.

## What NOT to do
- Don't call Perplexity, Crunchbase, PitchBook, Google Trends' API, or
  Apollo — that's the entire point of doing this pass manually.
- Don't add z-score/peer-relative normalization — Oscar explicitly said no
  (2026-08-06).
- Don't re-research `predictedWindowOpen`/`tier1FirmsOnCapTable` — those
  are already given in the input JSON from local data, not web research.
- In Cloud Shell, plain `git pull origin main` / `git push origin main` is
  correct — Cloud Shell's `origin` already points to
  github.com/ocachin/id8-intelligence. (This only gets confusing on one
  particular local sandbox where `origin` is misconfigured to an old repo
  and the real one is aliased `id8` instead — that's not the case in Cloud
  Shell, so don't add any special remote-name handling here.)
