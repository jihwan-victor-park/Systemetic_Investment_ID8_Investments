# Attio ↔ hub sync

Both directions, as of 2026-08-13. Before this, the only Attio → hub path was a
bulk pull someone had to remember to run, and the only hub → Attio path was the
stage dropdown.

```
                    NEW DEAL CREATED IN ATTIO
Attio workflow  ──────────POST, X-Attio-Webhook-Secret──────────▶  pipeline /attio-deal-created
(native, "Send                                                    (re-reads the deal from Attio,
 HTTP request")                                                    upserts the hub company doc)

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
   - URL: `https://id8-137750788450.us-east4.run.app/attio-deal-created`
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

**Secrets.** `ATTIO_WEBHOOK_SECRET` on the **`id8` pipeline** Cloud Run service
(us-east4), via Secret Manager — strip trailing newlines, see project memory.
Generate with `openssl rand -hex 32`. Nothing needs to change on hub-next.

**Why Attio calls the pipeline service directly.** The original design routed
Attio through hub-next's `/api/attio/deal-created`, on the belief that the
pipeline service was IAM-private and hub-next was the public front door.
Verified 2026-08-13 and both halves are backwards:

- **hub-next is behind Cloud IAP.** Any request without a Google-signed OIDC
  token gets a 302 to `accounts.google.com` and `Invalid IAP credentials: empty
  token`. Attio's "Send HTTP request" can only send static headers, so it can
  never reach that route.
- **The pipeline service answers the open internet, unauthenticated.**
  `curl https://id8-137750788450.us-east4.run.app/health` returns 200 from
  anywhere, and `INTERNAL_API_SECRET` is not set on it, so
  `_require_internal_secret` is a no-op on every route that calls it.

So the proxy hop bought nothing and blocked the flow. Attio now posts straight
to the pipeline route, authenticated by its own `ATTIO_WEBHOOK_SECRET` (see
`_require_attio_webhook_auth` — strict once the env var is set, and deliberately
a *different* secret from `INTERNAL_API_SECRET` so the value pasted into a
third-party UI doesn't also unlock `/update-deal-stage`). The hub-next proxy
route is left in place and still works over `X-Internal-Secret`; it's just no
longer on the path.

**This does not fix the wider gap.** Every other route on that service —
`/process*`, `/screen-deals`, `/screen`, `/sync-apollo`, `/publish-hub`,
`/backfill-*` — is still callable by anyone who knows the URL. See
`project_pipeline_app_auth_gap` and `docs/SYSTEM_AUDIT_2026-08-12.md`; closing
it means setting `INTERNAL_API_SECRET` here **and** adding
`PIPELINE_INTERNAL_SECRET` to hub-next's `cloudbuild.yaml` in the same change,
since nine hub-next routes send that header only when it's configured, and n8n's
`/process*` calls send no header at all.

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
