# n8n on Cloud Run — environment variable reference

These are set by `deploy.sh`. Listed here so you understand each one and can
tweak in the Cloud Run console later.

> **⚠️ Update (Jul 2026):** The Neon plan below was never what got deployed —
> `deploy.sh` connects to **Cloud SQL Postgres 16** instead (instance `n8n-db`,
> tier `db-f1-micro` as of Jul 2026, mounted via Unix socket
> `--add-cloudsql-instances`, ~$9/mo). See the actual variable names
> (`DB_POSTGRESDB_HOST=/cloudsql/<connection-name>`, etc.) in `deploy.sh`
> directly. Execution history is also pruned now via `EXECUTIONS_DATA_PRUNE=true`,
> `EXECUTIONS_DATA_MAX_AGE=336`, `EXECUTIONS_DATA_PRUNE_MAX_COUNT=10000` — not
> documented in the table below, also added straight to `deploy.sh`.

## Database (Cloud SQL Postgres — see update note above)

n8n's DB is tiny (workflow configs, credentials, execution logs, and since Jul
2026 that history is pruned to 14 days / 10k rows) — a shared-core `db-f1-micro`
instance comfortably covers it.

| Variable | Value | Notes |
|---|---|---|
| `DB_TYPE` | `postgresdb` | Switches n8n off its default SQLite (lost on every Cloud Run restart). |
| `DB_POSTGRESDB_HOST` | `/cloudsql/<connection-name>` | Unix socket path, set via `--add-cloudsql-instances`. |
| `DB_POSTGRESDB_DATABASE` / `DB_POSTGRESDB_USER` | `n8n` / `n8n` | |
| `DB_POSTGRESDB_PASSWORD` | *(secret)* | Stored in Secret Manager as `n8n-db-password`. |

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
