# PitchBook → Attio Pipeline

Automated deal flow pipeline for ID8 Investments. Processes weekly PitchBook exports and VC scout submissions, pushes deals into Attio CRM, and sends a formatted email digest to the team.

## How It Works

```
Google Drive (PB Weekly Drop)
        ↓  file uploaded
      n8n  (Google Drive Trigger)
        ↓  downloads file, POSTs raw Excel
  Render (Flask)
        ↓  transforms Excel → Attio API calls
     Attio  (deals + companies created/updated)
        ↓  returns deal list
      n8n  (Code node builds HTML)
        ↓
     Gmail  (digest sent to team)
```

A second workflow handles manual deal submissions from the VC scout via Google Sheets.

## Components

| Component | What it does |
|-----------|-------------|
| `app.py` | Flask service on Render. Receives raw Excel, transforms it, upserts deals and companies into Attio. |
| `transform_pitchbook.py` | Local-only script. Same transform logic — run manually to generate a clean CSV for review. |
| n8n workflow (PitchBook) | Google Drive Trigger → Download → POST to Render → build email HTML → Gmail digest. |
| n8n workflow (Scout) | Google Sheets trigger → normalize row → POST to Render → Attio. |

## Render Service

**URL:** `https://pb-attio-pipeline.onrender.com`

**Endpoints:**

- `POST /process` — accepts raw Excel binary or multipart `file` field. Returns created/skipped counts + deal list.
- `GET /health` — liveness check (used by UptimeRobot).
- `GET /debug/attributes` — lists all Deals object slugs from Attio (useful for debugging field mappings).

**Environment variables (set in Render dashboard):**

| Variable | Description |
|----------|-------------|
| `ATTIO_API_KEY` | Attio API key (Settings → API) |

## Attio Field Mapping

| PitchBook column | Attio slug | Type |
|-----------------|------------|------|
| Companies | `name` | text |
| Series | `series` | select |
| Description | `description` | text |
| Lead/Sole Investors | `lead_investors` | text |
| New Investors | `new_investors_7` | text |
| Deal Size | `deal_size` | currency |
| Post Valuation | `post_valuation` | currency |
| Revenue | `revenue` | currency |
| Valuation/Revenue | `valuation_revenue` | number |
| Deal Date | `deal_date` | date |
| Investors | `investors` | text |
| HQ Location | `location` | text |
| Company Website | `associated_company` (domain lookup) | record ref |

Companies are matched by domain and auto-created if not found.

## Local Transform Script

```bash
python transform_pitchbook.py
```

Reads the latest `.xlsx` from `~/Documents/` subfolders, outputs a clean CSV to `attio_import/`. Useful for spot-checking data before the automated pipeline runs.

## n8n Workflows

### 1. PitchBook Weekly (Google Drive Trigger)

1. **Google Drive Trigger** — watches "PB Weekly Drop" folder for new files
2. **Download file** — downloads the Excel as binary
3. **HTTP Request** — POSTs binary to `POST /process` on Render
4. **Code in JavaScript** — builds email HTML from returned deal list; outputs `{skip: true}` if no new deals
5. **If** — passes through only when `skip ≠ true`
6. **Send a message (Gmail)** — sends HTML digest to team

### 2. Scout Submissions (Google Sheets)

Reads new rows from the VC scout's Google Sheet and pushes them into Attio.

## Deployment

### Render

1. Connect the GitHub repo (`ocachin/pb-attio-pipeline`) in the Render dashboard
2. Set `ATTIO_API_KEY` in Environment variables
3. Render auto-deploys on every push to `main`
4. Runtime is pinned to Python 3.11.9 via `runtime.txt`

### n8n (Railway)

1. Deploy n8n on Railway using the official Docker image
2. Export workflows from local n8n: **Menu → Download**
3. Import JSON into Railway n8n instance
4. Reconnect credentials: Google OAuth (Drive + Gmail), HTTP Request header (`Authorization: Bearer <ATTIO_API_KEY>`)

### UptimeRobot

Create a free HTTP monitor pointing to `https://pb-attio-pipeline.onrender.com/health` with a 10-minute interval. This prevents Render's free tier from spinning down between workflow runs.

## Repo Structure

```
pb-attio-pipeline/
├── app.py                  # Flask service (Render)
├── transform_pitchbook.py  # Local CSV transform script
├── requirements.txt
├── runtime.txt             # python-3.11.9
└── README.md
```
