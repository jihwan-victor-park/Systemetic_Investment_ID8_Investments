# Attio ↔ hub sync

Both directions, as of 2026-08-13. Before this, the only Attio → hub path was a
bulk pull someone had to remember to run, and the only hub → Attio path was the
stage dropdown.

```
                    NEW DEAL CREATED IN ATTIO
Attio workflow  ──POST──▶  hub-next /api/attio/deal-created  ──▶  pipeline /attio-deal-created
(native, "Send                (public, X-Attio-Webhook-           (re-reads the deal from Attio,
 HTTP request")                Secret, no session)                 upserts the hub company doc)

                    EDIT MADE IN THE HUB
hub-next table  ──PATCH──▶  /api/companies/[slug]/{stage,round,deal-date}
                                     │
                                     ├─▶ Firestore (source of truth)
                                     └─▶ pipeline /update-deal-stage · /update-deal-fields ──▶ Attio
```

## Attio → hub: the native workflow to build

One workflow, fired on deal creation. Attio's trigger hands over a record id;
everything else is re-read server-side from Attio, so the body is one field.

1. **Attio → Automations → new workflow.**
2. **Trigger:** *Record created* → object **Deals**.
3. **Action:** *Send HTTP request*
   - Method: `POST`
   - URL: `https://<hub-next-url>/api/attio/deal-created`
   - Header: `X-Attio-Webhook-Secret: <the ATTIO_WEBHOOK_SECRET value>`
   - Header: `Content-Type: application/json`
   - Body:
     ```json
     { "record_id": "{{ record.id.record_id }}" }
     ```
4. Save and enable it. Create a throwaway deal in Attio and confirm it appears
   in the hub (in the tab matching its Attio stage, or Admin → Needs Triage if it
   has no stage yet), then delete the test deal.

**If the reference chip breaks.** Attio's chips are easy to mis-wire — see the
List-Entry-vs-Record mismatch documented in
[cc-attio-sync/README.md](../cc-attio-sync/README.md). The endpoint accepts
several shapes (`record_id`, `recordId`, `data.id.record_id`,
`events[].id.record_id` — see `_extract_attio_record_id` in `pipeline/app.py`),
so a differently-nested payload still works. What does NOT work is a chip that
renders as literal template text; that returns
`could not find a Deal record id in the request body` with the keys it did
receive, which is the fastest way to see what Attio actually sent.

**Idempotent by design.** The endpoint upserts on the same company slug every
other import path uses, so re-firing on an existing deal refreshes it instead of
duplicating it. The response's `created` flag says which happened. Safe to fire
on every creation, and safe for Attio to retry.

**Secrets.** `ATTIO_WEBHOOK_SECRET` on the hub-next Cloud Run service (via Secret
Manager, same as its other secrets — strip trailing newlines, see project
memory), plus the existing `PIPELINE_BASE_URL` / `PIPELINE_INTERNAL_SECRET`.
Generate with `openssl rand -hex 32`.

**Why it routes through hub-next.** The pipeline service holds the Attio
credential and the import logic, but it's IAM-private and this org's Domain
Restricted Sharing policy blocks making any Cloud Run service public (see
[cc-attio-sync/gateway/openapi.yaml](../cc-attio-sync/gateway/openapi.yaml) for
the API Gateway workaround that exists for the same reason). hub-next is already
public, so it provides the URL and forwards; the credential never moves. The
route is excluded from the session gate in `hub-next/src/middleware.js` — the
full path only, so the browser-triggered `/api/attio/import` stays gated.

## hub → Attio: what mirrors, and what deliberately doesn't

| Hub edit | Attio attribute | Route |
|---|---|---|
| Stage dropdown | `stage` (status) | `/update-deal-stage` |
| Series box | `series` (select) | `/update-deal-fields` |
| Deal Date picker | `deal_date` (date) | `/update-deal-fields` |

Those are the same slugs the import direction reads back
(`deal_intelligence/config.py`'s `READ_SLUGS`) — the point being that an edit
made in the hub lands where the next import looks, so it survives rather than
coming back as a reconciler conflict.

All three are **best-effort and non-blocking**: Firestore is the hub's source of
truth, a failed mirror is logged and not retried, and a company with no
`origin.attioRecordId` (created in the hub, never synced from Attio) has nothing
to push to and is skipped. An unknown Series option is created in Attio first
(`ensure_select_option`) rather than rejected.

Not mirrored: Radar Category, PitchBook URL, screen edits, tags. Those have no
Attio counterpart or no agreed direction of truth.

## What the import writes, and what it refuses to overwrite

`firestore_push.round_fields_patch` is the single rule, shared by all three
Attio → hub write paths (the webhook above, the bulk pull, and a screening run).

- **`round` (Series) fills only into a blank.** It's hand-editable in the hub,
  and hub-vs-Attio disagreements run in *both* directions — some hub values are
  ahead of Attio's, some behind — so a wholesale overwrite would destroy real
  research as often as it fixed staleness. Correcting a non-blank Series stays a
  deliberate call: `python3 -m deal_intelligence.deal_sync --apply-hub
  --overwrite-series --yes`.
- **`roundDate` / `roundSize` refresh whenever Attio disagrees.** External truth
  off Attio. A hub-side Deal Date edit is safe because it's pushed to Attio in
  the same call, so both sides already agree by the time any import runs. Dates
  compare on the first 10 characters, so an ISO timestamp and a plain date don't
  read as perpetually stale.

Before 2026-08-13 all three were written **on creation only**, so a company
already in the hub never picked up a Series or Deal Date that Attio learned
afterward — `deal_sync.py` kept finding and hand-repairing the same gap (7
blank Series, 11 stale dates on the 2026-08-13 run). That rule now lives in the
import path, so it corrects itself.

## Reconciling

`deal_intelligence/deal_sync.py` is still the audit: it reports what's on one
side and not the other, and where the two disagree about placement. It's now
mostly a *check* rather than the mechanism, since the live paths above fix the
common cases on their own.

```bash
python3 -m deal_intelligence.deal_sync --refresh
```

Read the report before passing `--apply-hub`, and read `--apply-hub`'s dry-run
output before adding `--yes`.

## Counting: why the hub's total won't match Attio's

Attio counts **deal records** — one per round. The hub counts **company docs**,
and folds multiple rounds of one company into a `companyKey` family with a
separate doc per extra round. On the 2026-08-13 snapshots:

| | count |
|---|---|
| Attio deal records | 339 |
| …distinct companies (27 hold 2+ deals) | 309 |
| Hub company docs (what the Dashboard's "Deals tracked" shows) | 336 |
| …of which additional-round docs | 22 |
| …base company docs | 314 |

So a ~30-deal gap between "Attio says N" and "the hub says M" is usually
multi-round companies, not missing data. The genuine gaps on that run were 8
Attio deals absent from the hub and 5 duplicate hub docs, both listed in the
sync report.
