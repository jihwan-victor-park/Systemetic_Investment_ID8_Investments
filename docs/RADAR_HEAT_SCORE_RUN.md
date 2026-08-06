# Running the Radar heat-score backfill (hand off to a separate chat, Haiku model)

## Why this doesn't need a research agent

`deal_intelligence/radar_backfill.py` already does the entire job as one
Python script — mandate screen, `capital_clock.compute()` (predicted raise
window), `radar_market_signals.research()` (a real Perplexity call per
company for news/momentum/step-up/traffic), `google_trends.py`, and
`radar_hazard.compute()` — then writes the result straight to each
company's `radar.*` fields in Firestore via `recompute_and_write()`. No
Claude web-browsing, no subagents. The only reason to run this from inside
a Claude Code chat at all is to babysit the run and report back — a Haiku
session is more than enough for that.

**Do not re-attempt the "spin up N research agents" approach** — that's
what burned through the previous session's rate limit for zero saved
output. This script replaces that entirely.

## What the new chat should do

1. Confirm scope first — dry run, no writes, cheap:
   ```
   cd ~/id8-intelligence && git pull origin main && python3 -m deal_intelligence.radar_backfill --dry-run
   ```
   Paste the output back. It should report on **61 companies** (10 primary
   `stage=='radar'` + 51 tag-only). If the count is off, stop and flag it —
   don't proceed to the real run on a mismatched population.

2. Sanity-check the dry-run output: every row should show a `heat=`,
   `growth=`, and `window=` value or a clear `FAIL (reason)`. `onyx` and
   `parallel` are known to have no round date on file — expect their
   `window=` to read `-` unless the Perplexity research below finds one.

3. Run it for real (this is the one that writes to Firestore and spends
   Perplexity API budget — real but small, ~61 calls):
   ```
   python3 -m deal_intelligence.radar_backfill
   ```
   This can take a few minutes (one Perplexity call + one Google Trends
   pair per company, sequential). Paste the final summary.

4. Report back: pass/fail counts, any company that errored outright (vs.
   a clean "FAIL (reason)" from the mandate screen, which is expected/fine),
   and whether `onyx`/`parallel` got a real window this time.

## What NOT to do
- Don't build or run Claude Agent/subagent web research for any of this —
  the script's own Perplexity call already covers it.
- Don't touch `radar_market_heat.py`'s scoring math (z-score, or anything
  else) — Oscar explicitly said not to add z-score normalization
  (2026-08-06).
- In Cloud Shell, plain `git pull origin main` / `git push origin main` is
  correct — Cloud Shell's `origin` already points to
  github.com/ocachin/id8-intelligence. (This only gets confusing on one
  particular local sandbox where `origin` is misconfigured to an old repo
  and the real one is aliased `id8` instead — that's not the case in Cloud
  Shell, so don't add any special remote-name handling here.)
