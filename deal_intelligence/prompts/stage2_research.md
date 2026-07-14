<!-- Stage 2 research angles (v3.1). Each is a separate Perplexity query;
results are synthesized into a memo. Documentation only -- ANGLES and
ANGLE_DEFINITIONS in stage2_research.py are the actual runtime source of
truth (this file isn't loaded by code); keep it in sync with that dict the
same way rubric.md's prose is kept in sync with rubric.py's PARAMS. -->

# Deep research angles

Run each of these as its own research query for the company in {deal}, only
for deals that already cleared the Stage 1 gate.

## Core angles

- **Company**: what they do, product architecture, founding team, headcount
  trend, key recent hires -- the baseline facts every other angle builds on.
- **Market**: size, growth, timing, structural tailwinds, and the real
  competitive set -- not just the company's own framing of its category.
- **Traction**: revenue scale and growth rate, customer/logo quality, net
  dollar retention, any public or credibly-estimated metrics. Label anything
  triangulated as `[ESTIMATED]` and show the triangulation math, per the
  rubric's estimation method -- never fabricate a number.
- **Round Dynamics**: who is leading, at what valuation and terms, and the
  full prior-round history. Verify -- do not assume -- whether the lead is
  genuine new money or a re-up: check cap table history, prior fund
  disclosures, or press coverage of earlier rounds. Also assess whether the
  source VC providing access is structurally pro-rata-constrained (small fund
  relative to check size, late fund vintage, concentration-capped) versus
  opportunistically selling access it could afford to keep.
- **Risks**: competitive, regulatory, key-person, technical, and financing
  risk -- and whether any single risk is severe enough to be a standalone
  concern rather than a footnote.

## Rubric-parity angles

These map 1:1 onto the two rubric dimensions most in need of independent
deep-research corroboration beyond Stage 1's cheaper pass:

- **AI Moat** (→ `ai_score`, 20%): does AI constitute the company's actual
  moat, or could this product become a plugin or default feature of Claude,
  GPT, or Gemini without material loss? Look for proprietary architecture or
  fine-tuning, a real data flywheel, in-house ML/research headcount and
  compute investment, and independent benchmarks -- versus a thin wrapper
  over third-party foundation-model APIs.
- **Return Potential** (→ `return_potential`, 20%): base-case MOIC/IRR
  realism at the current entry price, exit path clarity (IPO readiness,
  active M&A appetite, comparable exits), and dilution modeling across at
  least two future financing rounds (~20-25% each). Check whether the company
  appears on Setter Capital's quarterly "Setter 30" or is reported as
  actively traded on Forge, Caplight, EquityZen, or similar secondary
  marketplaces, as an external, checkable corroboration of the modeled exit
  thesis -- not a substitute for it.

## Additional screening factors

Deck-sourced supplementary factors (ID8 Growth Opportunities Fund I deck,
p.13, "Additional Multi-Factor Analysis for Further Optimization") that sit
alongside the core rubric rather than mapping onto a single dimension:

- **Capital Efficiency**: how lean is the preferred capital stack to date? A
  lean stack signals robust value creation and a real equity cushion; a
  stacked, senior-heavy cap table erodes both.
- **Lead Conviction**: who is leading the round, and do they have a track
  record plus real capital commitment (skin in the game) -- a specific
  partner's reputation and personal co-invest, not just the fund's brand?
- **Institutional Momentum**: which Tier 1 investors are already in the cap
  table, and are they following on alongside the new lead -- a distinct,
  corroborating signal from the new-money lead itself, not the same fact
  restated.
- **Foundational Quality**: is the founding team reputable, and is the
  valuation defensible given the stage and comps (Rule-of-40-style,
  growth-adjusted)?

For each angle, return concise findings with sources. Never fabricate.
