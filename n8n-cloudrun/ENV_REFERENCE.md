# n8n on Cloud Run — environment variable reference

These are set by `deploy.sh`. Listed here so you understand each one and can
tweak in the Cloud Run console later.

## Database (Neon serverless Postgres — free)

Free tier at https://neon.tech. n8n's DB is tiny (workflow configs, credentials,
execution logs) — Neon's 0.5GB free tier is more than enough indefinitely.

| Variable | Value | Notes |
|---|---|---|
| `DB_TYPE` | `postgresdb` | Switches n8n off its default SQLite (lost on every Cloud Run restart). |
| `DB_POSTGRESDB_URL` | *(secret)* | Full Neon connection string. Stored in Secret Manager as `n8n-database-url`. Format: `postgres://user:pass@host/dbname?sslmode=require` |

No Cloud SQL instance needed. No `--add-cloudsql-instances` flag. No $25/mo bill.

## Identity & security

| Variable | Value | Notes |
|---|---|---|
| `N8N_ENCRYPTION_KEY` | *(secret)* | **Most important value.** Encrypts stored credentials. Must stay constant forever. To migrate existing local credentials, reuse your local key from `~/.n8n/config`. |

## Networking / URLs

| Variable | Value | Notes |
|---|---|---|
| `N8N_PORT` | `5678` | Must match the Cloud Run `--port`. |
| `N8N_PROTOCOL` | `https` | Cloud Run terminates TLS. |
| `N8N_HOST` | `<service>.run.app` | Hostname only, no scheme. |
| `N8N_EDITOR_BASE_URL` | full https URL | Used for links in the UI. |
| `WEBHOOK_URL` | full https URL | **Critical** — webhook + OAuth callback base. OAuth redirect becomes `<WEBHOOK_URL>/rest/oauth2-credential/callback`. |
| `GENERIC_TIMEZONE` | `America/New_York` | Affects schedule/cron triggers. |

## Behavior

| Variable | Value | Notes |
|---|---|---|
| `N8N_RUNNERS_ENABLED` | `true` | Enables task runners (recommended/required in recent n8n for Code nodes). |
| `N8N_DIAGNOSTICS_ENABLED` | `false` | Opt out of telemetry. Optional. |

## Cloud Run flags that matter (not env vars)

- `--min-instances=1` + `--no-cpu-throttling` — keeps n8n running 24/7 so your
  **every-minute Google Drive polling** and any schedule triggers keep firing.
  Without this, Cloud Run scales to zero and triggers silently stop.
- `--max-instances=1` — n8n in default ("regular") mode is single-instance.
  Two instances would poll Drive twice and double-process files. Scaling beyond
  one requires **queue mode** (Redis + separate worker services) — overkill for
  your volume.
- `--add-cloudsql-instances` — mounts the Cloud SQL socket.
- `--timeout=3600` — max request time (UI streaming / long executions).
