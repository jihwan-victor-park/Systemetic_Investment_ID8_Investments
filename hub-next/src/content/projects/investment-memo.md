---
title: Investment Memo Generator
description: Multi-agent system that writes a complete ID8 investment memo from raw deal data.
---

import GuideCard from '@site/src/components/GuideCard';

# Investment Memo Generator

The Investment Memo Generator turns raw deal data — a pitch deck, term sheet, PitchBook profile, or just a company name and round details — into a complete, formatted DOCX investment memo in the ID8 canonical style. A 16-agent workflow handles intake, research, parallel section writing, and editorial assembly. The output reads like the Polymarket, Saronic, and Hadrian memos the format was derived from.

<GuideCard
  title="Investment Memo Generator"
  meta="The formatted edition. Workflow, sections, output format, and reference."
  cover="/img/cover_investment_memo.png"
  docx="/guides/ID8_Investment_Memo_Generator_Guide.docx" />

| | Detail |
| --- | --- |
| Invoke | `/investment-memo` in Claude Code |
| Output | `.docx` file, ~4,000–7,000 words across 14 sections |
| Data sources | User documents + PitchBook + web search (auto-filled on gaps) |
| Runtime | 15–20 minutes, ~500k tokens |

## How to use it

Type `/investment-memo` in Claude Code. Before the workflow runs, Claude will ask for any missing inputs. The minimum you need is a company name, deal type, and basic round terms. Everything else can be sourced from PitchBook and the web automatically.

**Fastest path:** provide the company name and deal description. The intake agent fills the rest.

:::note
The workflow takes 15–20 minutes and consumes roughly 500k tokens across its 16 agents. Run it only on deals that have cleared initial review.
:::

**Richest output:** attach a pitch deck, term sheet, and financial model before running. The agents prioritize your documents over external sources and flag any conflicts with external data.

### What to provide

| Input | Notes |
| --- | --- |
| Company name | Required |
| One-line description | Optional — intake agent will draft one if missing |
| Deal type | e.g. "Series D — Preferred Stock", "Founder Secondary — Common Stock" |
| Round terms | Security type, round size, pre-money, post-money, lead investor, prior round |
| Memo date | e.g. "June 2026" |
| Attached documents | Pitch deck, financial model, term sheet, IC presentation — all optional but each one adds depth |

:::note
If your data conflicts with what PitchBook or web search returns (e.g. a different valuation), Claude surfaces the conflict before running and uses your figure unless you say otherwise.
:::

## The workflow

The workflow runs four sequential phases with 16 agents total.

```
Intake  →  Brief  →  Write (14 agents in parallel)  →  Edit
```

| Phase | What happens |
| --- | --- |
| **Intake** | One agent digests all raw input — your documents, PitchBook data, and web research — into a structured company brief. Data gaps are flagged as `DATA GAP:`. Conflicts are flagged as `CONFLICT: user says X, external says Y`. |
| **Brief** | The structured brief is packaged into 14 section-specific data blocks, each containing only the facts relevant to that section. |
| **Write** | 14 agents run in parallel, each writing one section independently from its brief. Agents write to the style guide: institutional voice, no hedging in body text, every paragraph anchored to a specific figure or named entity. |
| **Edit** | One editorial agent assembles all 14 sections, adds cross-references between sections, verifies internal consistency, and finalizes the complete memo. |

## The 14 sections

| # | Section | What it covers |
| --- | --- | --- |
| 1 | **Investment Overview** | Executive summary — thesis bullets, key risks, conviction statement. Reader who only reads this understands the full thesis. |
| 2 | **Investment Highlights** | 4–5 named thesis pillars, each a bold H2 followed by 2–3 quantified prose paragraphs. No bullets — all analytical narrative. |
| 3 | **Business Overview** | What the company builds, sells, and operates. Product table if hardware or multi-product; "What Trades" table if marketplace. |
| 4 | **Revenue Model** | One H2 per revenue stream: mechanism, current scale, and projected unit economics. |
| 5 | **Addressable Market** | TAM methodology, why the market is expanding now, company's current penetration vs. TAM. |
| 6 | **Founder & Management Team** | One H2 per founder or key exec: prior companies, exits, domain credentials. Advisory board if notable. |
| 7 | **Raise Timeline** | Full funding history table: Round — Date — Size — Post-Money — Lead Investor(s). |
| 8 | **Competitor Overview** | Competitive landscape narrative + 4–7 row competitor matrix with threat level and rationale per competitor. |
| 9 | **Lead Investor** | Strategic profile, fund performance table, and a section on why this lead chose this company. |
| 10 | **Financial Snapshot** | Key metrics table: revenue, growth, gross margin, EBITDA, valuation, revenue multiple. Footnoted source and date. |
| 11 | **Valuation** | Comps table (5–8 private and public peers), entry multiple analysis, path to multiple re-rate, optional scenario analysis. |
| 12 | **Exit & Monetization Considerations** | IPO path, strategic acquisition (named buyer universe), secondary liquidity. Bear/Base/Bull exit scenario table. |
| 13 | **Risk Factors** | 5–6 named risks. Each: 2–4 sentence problem citing specific entities → mitigant bullet 3–5× longer, naming partners, dates, and programs. |
| 14 | **Key Investment Assumptions** | 5–7 numbered, falsifiable assumptions the thesis depends on — specific enough to monitor as the deal ages. |

## Output format

The output is a `.docx` file built to the ID8 canonical style. Typography, table formatting, color palette, and section spacing all match the reference memos exactly.

| Element | Style |
| --- | --- |
| Section headings | Roboto Serif 16pt bold, bottom border rule |
| Body text | Sora 11pt justified, #1a1a1a |
| Table headers | Sora 9pt bold white on #1a1a1a |
| Table rows | Alternating #f5f5f5 / white |
| Exit scenario rows | Bear = amber (#fff6e5), Bull = green (#eaf3de) |
| Footer | Page number, Sora 8.5pt #828282, centered |

The file saves to your Downloads folder by default. You can specify a different path when prompted.

## Writing voice

Agents write in the same institutional style throughout.

- **Declarative and third-person.** No first-person. No hedging in body text — hedging belongs only in footnotes.
- **Quantitatively dense.** Every paragraph contains at least one specific dollar figure, percentage, date, or named entity.
- **No superlatives.** Precise comparative framing: "the only company that simultaneously holds X, Y, and Z" not "the best."
- **Cross-references named explicitly.** Sections refer to each other: "discussed in detail in the Risk Factors section."
- **Data attributed.** Figures cite their source: "per PitchBook", "per management", "per Bloomberg".

## Data gap behavior

When the intake agent cannot find data for a required field, it writes a `DATA GAP:` placeholder so the editorial agent and you can see exactly what is missing. It will not invent figures. If a section has too many gaps to write substantively, it is flagged for manual review in the final report.

## Technical reference

| File | Role |
| --- | --- |
| `.claude/skills/investment-memo/scripts/workflow.js` | Workflow orchestration — 4 phases, 16 agents |
| `.claude/skills/investment-memo/scripts/build_memo.py` | DOCX builder — converts JSON memo output to formatted Word file |
| `.claude/skills/investment-memo/references/style-guide.md` | Typography, color palette, table system, writing voice |
| `.claude/skills/investment-memo/references/section-guide.md` | Per-section structure, length targets, analytical requirements |
