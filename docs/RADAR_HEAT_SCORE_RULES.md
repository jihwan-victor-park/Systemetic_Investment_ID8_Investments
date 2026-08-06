# Radar Heat Score Signal Framework — rules for manual web research

Source: Oscar's `Heat Score Signal Framework.xlsx`, as already coded in
`deal_intelligence/radar_market_heat.py`. This doc restates the same rubric
for an agent that will research each signal itself via its own web
search/fetch tools — **not** via Perplexity, Crunchbase, Google Trends, or
Apollo. Those are the 3rd-party APIs the codebase's version uses; this run
replaces all of them with the agent's own browsing.

## Hard rules

1. **"Unknown" is a correct, expected answer.** A private company with no
   public coverage of its traffic, valuation history, or Reddit activity is
   the NORMAL case, not a research failure. If you can't find real public
   evidence for a signal, mark it `"computed": false, "raw": null` —
   **never** guess or default to a middle value. A guessed 0 reads as "the
   market is cold on this company," which is a false claim you have no
   evidence for.
2. **Confirm company identity before using any source.** Multiple unrelated
   companies share the same or similar names. Before citing a source,
   confirm it's actually about the company at the given domain/description
   — not a different company with the same name. If ambiguous, discard it.
3. **Cite your source** for every signal you DO score — a URL, not just a
   claim.
4. **No 3rd-party research APIs.** Use your own web search/fetch only. Do
   not call Perplexity, Crunchbase, PitchBook, Google Trends, or Apollo —
   this run is specifically to avoid depending on those integrations.
5. Two signals (`momEmployeeGrowth`, `jobPostingVelocity`) need Apollo/ATS
   data this agent has no access to. Leave them `computed: false` always —
   don't attempt to estimate headcount trends from LinkedIn scraping or
   similar; that's out of scope for this pass.

## The 16 signals

| # | Signal | Weight | How to score it (0–10) |
|---|--------|--------|--------------------------|
| 1–2 | Latest Round / Est. Time Between Rounds | (inputs only, 0 weight) | Already given in the company JSON (`round`, `roundDate`) — don't re-research. |
| 3 | **Raise Probability** | 15 | Already computed for you as `predictedWindowOpen`/`windowBasis` in the company JSON (local cadence math, not web research). Don't re-derive — just carry it through. |
| 4 | **Industry Growth** | 10 | All of the company's industry/sector tags — avg % change in public search/press interest in that industry vs. the preceding month. 10 = avg up >25%; 7 = +10–25%; 5 = flat (±10%); 0 = down >10%. |
| 5 | MoM Employee Growth | 2.5 | **Not researchable this pass** (needs Apollo). Leave `computed:false`. |
| 6 | Job Posting Velocity | 2.5 | **Not researchable this pass** (needs ATS access). Leave `computed:false`. |
| 7 | Crunchbase Growth Score | 5 | Shares ONE "public momentum" read with #14/#15 below — see that row. |
| 8 | **Step-Up** | 5 | Valuation vs. prior round, ONLY if both rounds' valuations are publicly disclosed (rare for private companies). 10 = 2.0x+; 8 = 1.5–2.0x; 6 = 1.0–1.5x; 4 = flat (~1.0x); 0–2 = down round. If not both disclosed: unknown. |
| 9 | **YoY Revenue/ARR Growth** | 5 | From any public reporting (news, company statements). 10 = >100% YoY; 8 = 75–100%; 6 = 40–75%; 4 = 20–40%; 0–2 = <20%/declining. |
| 10 | **News Volume** | 10 | Articles/press mentions in the last ~90 days. 10 = above average for a company this size/stage; 5 = steady baseline coverage; 0 = little/no coverage. |
| 11 | **Monthly Website Visits Growth** | 5 | Only if a public source (news, a public SimilarWeb-style report) explicitly states a traffic trend. 10 = >20% growth; 7 = 10–20%; 5 = 0–10%; 3 = flat; 0 = declining. |
| 12 | **Google Trends search interest** | 10 | Public search-interest trend for the company name vs. the preceding month (Google Trends is public/free to check directly, just don't use the `pytrends` API path). 10 = up >25%; 7 = +10–25%; 5 = flat (±10%); 0 = down >10%. |
| 13 | **Reddit activity** | 5 | Trailing 30-day mention/engagement volume vs. the prior 30 days, searched directly. 10 = clear sustained uptick; 5 = steady baseline; 0 = little/none. |
| 14 | Crunchbase Heat Score | 10 | Same "public momentum" read as #7/#15 — see below. |
| 15 | Crunchbase Surge Score | 5 | Same "public momentum" read as #7/#14 — see below. |
| 16 | **Tier 1 Investor Count** | 10 | Already given in the company JSON (`tier1FirmsOnCapTable`). Don't re-research — 10 = 3+ Tier 1 firms; 7 = 2; 4 = 1; 0 = none. |

**Rows #7/#14/#15 (Crunchbase Growth/Heat/Surge Score) — ONE shared read:**
these three rows only have real numbers inside a paid Crunchbase Pro
session. Don't fabricate three different numbers. Instead, form ONE
judgment — "strong" / "moderate" / "weak" / unknown — of overall public
momentum (funding rumors, notable hires, product launches, partnerships,
expansion news, analyst commentary), and apply the SAME score to all
three: strong=10, moderate=5, weak=0, unknown=`computed:false`. Label each
of the three with a note that it's a momentum-proxy, not Crunchbase's own
score.

## Scoring math (must match exactly — this is what the codebase does)

For each signal: `contribution = raw_score / 10 * weight` (only when
`computed: true`).

```
pointsAvailable = sum(weight for every signal where computed=true)
contributionTotal = sum(contribution for every signal where computed=true)
score = min(contributionTotal, 100)              # never let missing signals shrink it
normalizedScore = min(contributionTotal / pointsAvailable * 100, 100)
```

`normalizedScore` is the one to actually compare across companies (it
answers "of what we could measure, how hot" — not penalized by how many of
the 16 rows happen to be researchable for a given company).

## Output format — one JSON object per company

```json
{
  "id": "altaclaro",
  "signals": {
    "industryGrowth": {"computed": true, "raw": 7.0, "evidence": "...", "source": "https://..."},
    "stepUp": {"computed": false, "raw": null},
    "...": "...all 16 keys, always present"
  },
  "score": 42.3,
  "normalizedScore": 61.0,
  "pointsAvailable": 70,
  "notComputed": ["momEmployeeGrowth", "jobPostingVelocity", "stepUp", "..."],
  "researchedAt": "2026-08-06"
}
```

Signal keys to use (must match exactly, camelCase):
`raiseProbability, industryGrowth, momEmployeeGrowth, jobPostingVelocity,
crunchbaseGrowthScore, stepUp, yoyRevenueGrowth, newsVolume,
websiteVisitsGrowth, googleTrendsSearchInterest, redditActivity,
crunchbaseHeatScore, crunchbaseSurgeScore, tier1InvestorCount`. (16 rows,
minus the 2 input-only rows = 14 scored signal keys per company.)

## What NOT to do
- Don't add z-score/peer-relative normalization — Oscar explicitly said no
  (2026-08-06).
- Don't call Perplexity, Crunchbase, Google Trends' API, or Apollo.
- Don't touch Firestore directly from this research pass — just produce
  the scored JSON. Writing it back is a separate step.
