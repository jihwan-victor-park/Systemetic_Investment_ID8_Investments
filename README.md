# pb-attio-pipeline

Flask service that ingests deal data (PitchBook exports, Jesse's deal sheet) and
upserts it into [Attio](https://attio.com), then hands a clean payload back to
n8n which renders and sends the deal-flow emails.

```
PitchBook .xlsx ─┐
Watchlist .xlsx ─┼──▶  n8n  ──▶  Flask (this service)  ──▶  Attio API
Jesse's Sheet   ─┘                      │
                                        └──▶  JSON { deals: [...] }  ──▶  n8n Code node ──▶  email
```

The service is stateless — it transforms whatever it's given, writes to Attio,
and returns the created deals. All scheduling, file fetching, and email sending
lives in n8n.

## Endpoints

| Route | Method | Purpose | Stage / Source |
|---|---|---|---|
| `/process` | POST | PitchBook xlsx → Attio deals | `Qualified` / `ID8 Investments` |
| `/process-watchlist` | POST | PitchBook xlsx → Attio deals | `Watchlist` / `ID8 Investments` |
| `/process-jesse` | POST | Single deal (JSON) → Attio | `Watchlist` / `Jesse` |
| `/logo` | GET | Serves `logo.png` for email headers | — |
| `/health` | GET | Health check | — |
| `/debug/attributes` | GET | Lists the Deals object's attribute slugs/types | — |

`/process` and `/process-watchlist` accept the raw xlsx as the request body or as
a `file` multipart upload. `/process-jesse` accepts one deal as a JSON object
(keys: `Company`, `Round`, `Company Website`, `Description`, `Deal Size`,
`Post Valuation`, `Revenue`, `Date`, `Lead Investor`, `New Investors`, `Access`).

All three return:

```json
{ "status": "done", "created": 2, "skipped": 1, "errors": [], "deals": [ ... ] }
```

The `deals` array drives the email — it contains **only deals that were freshly
created** this run. Already-existing deals are skipped and do not reappear in the
email.

## How numbers are handled

**PitchBook and Jesse money values arrive in `$millions`** — `400` means $400M,
`44000` means $44B, `1163.11` means $1.163B.

- **Into Attio:** all currency fields (`Deal Size`, `Post Valuation`, `Revenue`)
  are multiplied by 1,000,000 before being stored, so Attio holds the real
  amount (`400` → `$400,000,000`). See `MILLION` / `build_attio_values` in
  [app.py](app.py).
- **`Valuation/Revenue` is a ratio, not money** — it is stored as-is, never scaled.
- **Into the email:** `deal_size` and `post_valuation` are pre-formatted by the
  server via `fmt_money_millions` into display strings (`$400M`, `$1.16B`). The
  n8n email Code node prints these strings directly — it must **not** re-parse
  them, or a `$1.16B` gets mis-rendered as `$1.16M`. Revenue is stored in Attio
  but is not shown in the email.

## Select options auto-create

When a deal has a `select` value (e.g. `Series`) that doesn't yet exist in
Attio's picklist — like a new `Series A2` — `ensure_select_option` creates the
option via the Attio attributes API before writing the deal, so the write
doesn't fail. Existing options are cached per attribute for the run.

## Deduplication

`find_deal` matches an existing deal on **company name + series** and returns its
record id; `upsert_deal` then skips creation (returning `"skipped"`). Companies
are matched/created by normalized domain (`find_or_create_company`).

> ⚠️ Dedup keys off the Attio record. If a deal is deleted from Attio, a re-read
> of the same source row will re-create it (and re-email it). See gotchas below.

## Running locally

```bash
pip install -r requirements.txt
export ATTIO_API_KEY=sk_...
python app.py            # serves on :8080 (or $PORT)
```

Production runs under gunicorn (e.g. on Render):

```bash
gunicorn app:app
```

### Environment

| Var | Required | Default |
|---|---|---|
| `ATTIO_API_KEY` | yes | — |
| `PORT` | no | `8080` |

## Repo contents

- `app.py` — the Flask service (the deployed artifact).
- `transform_pitchbook.py` — standalone CLI to clean a PitchBook xlsx to CSV
  (same column logic as the service; useful for manual/offline runs).
- `attio_import/` — sample cleaned CSV output.
- `logo.png` — ID8 logo served at `/logo` for email headers.

## Gotchas

- **Stale test rows in Jesse's sheet.** The Jesse workflow reprocesses the whole
  sheet each run and filters on `Ready = TRUE` / `Access = TRUE`. Leftover test
  rows with those flags set (e.g. `PanchoPollo`, `hOLA`) get re-sent and re-created
  every run. Delete test rows, or add a `Sent` column and filter on it so each row
  is only processed once.
- **Deploy app + email node together.** The emails depend on the server sending
  pre-formatted money strings. If you update the n8n Code nodes before deploying
  the matching `app.py`, money fields render wrong until both sides match.
- **n8n pinned data.** Pinned node output from manual testing replays on later
  manual executions — unpin nodes if old test deals appear with an empty source.
