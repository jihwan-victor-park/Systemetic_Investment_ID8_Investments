---
title: PitchBook → Attio Pipeline
description: Syncing PitchBook deal, company, and investor data into Attio.
---

import GuideCard from '@site/src/components/GuideCard';

# PitchBook → Attio Pipeline

This pipeline reads PitchBook exports of deals, companies, and investors and writes them into ID8's Attio CRM. It creates and updates Deal and Company records, stages deals, and links each deal to the VC firms that invested so the investor graph in Attio stays accurate.

<GuideCard
  title="PitchBook → Attio Pipeline"
  meta="The formatted edition. Investor linking, write formats, and backfill."
  cover="/img/cover_pitchbook.png"
  docx="/guides/ID8_PitchBook_Attio_Pipeline_Guide.docx" />


| | Detail |
| --- | --- |
| Input | A PitchBook CSV of deals and companies, ideally with the Investors Websites column |
| Output | Attio Deals and Companies, staged, with lead, new, and all-investor links |
| Code | pipeline/ (app.py, attio_apollo_sync.py, attio_import/) |

:::note
The most important column in your export is Investors Websites. Without it, only VCs that already exist in Attio by name get linked. Everything else is skipped.
:::

## How it works

1. Export deals and companies from PitchBook, including the Investors Websites column.
2. Run the processing endpoint. Records are matched or created in Attio.
3. Deal stage is applied per the staging rules below.
4. Investor references are resolved and written as record links.

### Write values are not read values

Attio's write format for a value differs from its read format. Writing the read shape fails silently. The field just does not get set, with no error. This is the most common reason a field looks like it did not update.

| Type | Write format |
| --- | --- |
| select, single | plain string of the option title, like `"slug": "Yes"`. Not `[{"option":"Yes"}]` |
| multi-select | array of title strings, like `"slug": ["A", "B"]` |
| text | `[{"value": "..."}]` |
| number | `[{"value": 123}]` |
| currency | `[{"currency_value": 123}]`. Money in millions, so multiply by 1,000,000 |
| date | `[{"value": "YYYY-MM-DD"}]` |
| status | `[{"status": "Watchlist"}]` |
| record reference | `[{"target_object": "companies", "target_record_id": "..."}]` |

:::note
A single-select must be a plain string. The `[{"option": "Yes"}]` shape is the read format and is ignored on write. This is why `top_10_vc` used to not get set. An unknown option errors, so `ensure_select_option` creates it first.
:::

## Investor linking

The Deals object links VC firms to Company records through reference attributes. The link slugs, held in INVESTOR_REF_MAP, are below.

| Category | Reference slug |
| --- | --- |
| Lead investors | lead_investors_8 |
| New investors | new_investors_5 |
| All investors, including follow-ons | investors_5 |

:::note
These are different from the text slugs in FIELD_MAP, which are `lead_investors`, `new_investors_7`, and `investors`. Those drive email and display. The slugs above create the actual links.
:::

### Domain versus record ID

These are two different mechanisms depending on whether you use the CSV importer or the API.

The CSV importer links by domain. Put the company domain in the cell and match on Domains. Record-ID matching does not work reliably in the importer. Separate multi-value cells with a comma and a space, not a semicolon.

The API links by `target_record_id`. There is no link-by-domain in the API. resolve_investor_links matches by domain first, then by name, then sends the resolved id. Do not change it to emit a domain or the call breaks.

### Create if website

resolve_investor_links matches by domain first, then name. If an investor is unmatched and the export gave its domain, it creates the company and caches the new id so repeats reuse it. Unmatched with no domain gets skipped, since you cannot create a company without a domain.

## Backfill, staging, and fixes

### Bulk backfill, use CSV not the API

get_company_index with refresh pages every Company. On a large workspace that alone passes the 30 second gunicorn timeout, so `/process`, `/backfill-investors`, and `/update-investors` all return 500.

For a one-off backfill, do not fight the timeout. Build a CSV locally and import it to Deals in the Attio UI.

1. One row per deal, with domain columns per category, multi-value separated by a comma and a space. pandas quotes the cells for you.
2. Reuse `parse_investor_websites` for the name-to-domain map and `parse_investors` per category.
3. Import to Deals: match deals by Name, map domain columns to `lead_investors_8`, `new_investors_5`, and `investors_5`, match target Companies on Domains, and create missing ones.

:::note
Duplicate deal names across Series make name-matching ambiguous. Handle those by Series or by hand.
:::

### Staging rules

`/process-top10` puts only new deals on Radar. Existing deals keep their current stage, so do not auto-promote a Qualified deal. To bulk-promote existing Qualified deals to Radar, use `/fix-radar-stages`. It moves Qualified deals that have `new_investors_7`.

## Technical structure

Code lives in `pipeline/` (`app.py`, `attio_apollo_sync.py`, `attio_import/`). The endpoints above run from `pipeline/app.py`.
