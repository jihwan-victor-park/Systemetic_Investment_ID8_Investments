---
title: Apollo Reach Out
description: Building clean family office and RIA lists, enriching them, and launching sequences.
---

import GuideCard from '@site/src/components/GuideCard';

# Apollo Reach Out

Apollo Reach Out turns Apollo's contact database into a short, clean list of real family office and RIA decision-makers. It enriches each one and loads them into a managed outbound sequence.

<GuideCard
  title="Apollo Reach Out"
  meta="The formatted edition. Filters, enrichment, and sequence setup."
  cover="/img/cover_apollo.png"
  docx="/guides/ID8_Apollo_Reach_Out_Guide.docx" />

The hard part is filtering. A broad search for financial services in Los Angeles returns about 61,889 people. That is every banker, broker, and fintech employee in the city. This guide is the recipe that gets you down to 50 to 300 real prospects.

## When to use it

- You are preparing an outbound push for a city or an event, like the LA trip.
- You need a fresh list of prospects to feed the LP screener.
- You want to load qualified contacts into a sequence without touching anyone already in a live campaign.

## What you get

| Stage | Output |
| --- | --- |
| Filtered search | 50 to 300 clean FO and RIA decision-makers in the target city |
| Enrichment | Research and a 0 to 100 LP fit score per firm |
| Sequence load | Contacts mirrored into Apollo and enrolled in the managed sequence |

:::note
Quality beats quantity here. A hundred precise contacts outperform five thousand broad ones. If loosening a filter grows the list, the list usually got worse.
:::

## Building the target list

Set the filters in this order. Each layer removes a category of bad results. The employee count filter does most of the work on its own.

### Step 1. Company keywords to include

Set the keyword type to ANY so a contact matches on any single term. Use only the terms real family offices use about themselves.

- family office
- single family office
- multi-family office
- private family office
- family wealth
- private wealth

:::note
Skip the broad terms wealth management, investment management, and financial services. They pull in large platforms like Mercer, Edward Jones, and Raymond James.
:::

### Step 2. Company keywords to exclude

Exclusions do more work than inclusions. Paste these into the exclude box.

| Category | Exclude terms |
| --- | --- |
| Banks and wirehouses | bank, banking, brokerage, broker dealer, Raymond James, Edward Jones, Morgan Stanley, Wells Fargo, Merrill Lynch, UBS, Charles Schwab, Ameriprise, LPL Financial |
| Large platforms | Fidelity, Vanguard, BlackRock, asset management, fund administration |
| Insurance | insurance, Northwestern Mutual |
| Wrong asset class | hedge fund, private equity, venture capital, real estate |
| Wrong kind of finance | accounting, tax, payroll |
| Tech in finance | fintech, software, technology |

### Step 3. Employee count

Real family offices have 2 to 30 employees. Platforms have hundreds or thousands. Under Company Headcount, select 1 to 10 and 11 to 50.

:::note
This one filter removes about 90 percent of the wrong results. If you do nothing else, do this.
:::

### Step 4. Job titles

Partner, Managing Partner, Principal, Chief Investment Officer, Head of Investments, Director of Investments, Managing Director, Investment Director, Portfolio Manager.

### Step 5. Seniority

Owner or Partner, C-Suite, VP, Director.

### Step 6. Location

Keep the geography tight to the campaign. For the current effort this is Los Angeles.

### RIA sub-search

RIAs that serve high-net-worth clients are small firms. Run them as a separate search.

| Filter | Value |
| --- | --- |
| Keywords | registered investment advisor OR RIA |
| Headcount | 1 to 50 |
| Titles | Partner, CIO, Managing Director, Principal |

Any RIA with 500 or more employees is a retail platform, not what you want.

### What good looks like

After all layers you should land between 50 and 300 results. You want unfamiliar names like Westlake Capital or Meridian Family Office. If you recognize the firm, it is too big.

## Enrich and launch

### Enrich with Perplexity

Research each firm before you reach out. The enrichment step scores each firm against the ID8 Growth Opportunities Fund I rubric.

| Script | Role |
| --- | --- |
| perplexity_lp_screener.py | Per-firm web research and structured notes |
| lp_screener_hybrid.py | Applies the 0 to 100 rubric and tiers firms |

These also back the `lp-prospect-screener` skill. Hand it a CSV of contacts and it returns a scored, tiered CSV.

:::note
Screen before you load the sequence. Enroll only Tier 1 and Tier 2 firms.
:::

### Load the sequence

The sync mirrors your Attio People into Apollo and parks them in a dormant holding sequence. Any later Apollo search then flags those people as already sequenced, so you never double-touch a contact. It lives in `pipeline/attio_apollo_sync.py` and runs from `/sync-apollo`.

```bash
curl -X POST https://<your-app>/sync-apollo
curl https://<your-app>/sync-apollo/status
```

| Env var | Notes |
| --- | --- |
| APOLLO_API_KEY | Must be a master key. add_contact_ids returns 403 otherwise |
| APOLLO_HOLDING_SEQUENCE_ID | A dormant sequence with no active email steps |
| APOLLO_MAILBOX_ID | Optional mailbox for the sequence |

### API gotchas

These fail silently with no error, so they are easy to miss.

- `add_contact_ids` needs a master API key.
- Sequence flags are snake_case: `sequence_active_in_other_campaigns` and `sequence_finished_in_other_campaigns`. CamelCase is ignored. Keep both false so live contacts stay put.
- The mailbox param is `send_email_from_email_account_id`, and `emailer_campaign_id` must echo the sequence id.
- Upsert with `POST /contacts` and `run_dedupe=true`. The lookup fallback is `POST /contacts/search`.
- Re-running is safe. Apollo dedupes and a contact can only sit in a sequence once.

## Technical structure

Code lives in `pipeline/attio_apollo_sync.py` (the sync, exposed at `/sync-apollo`), `lp-screener/` (`perplexity_lp_screener.py` and `lp_screener_hybrid.py` for enrichment and scoring), and the `lp-prospect-screener` skill.
