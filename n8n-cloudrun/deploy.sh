#!/usr/bin/env bash
#
# Deploy self-hosted n8n to Google Cloud Run, backed by Cloud SQL Postgres.
# Workflow triggers are native Google Drive Trigger / Sheets nodes inside n8n
# (polling), which requires the instance to stay warm — Cloud Run cannot run
# a background timer while scaled to zero. Previously this used webhooks
# fired by an external Apps Script watcher (drive-watcher.gs) so Cloud Run
# could scale to zero; that approach was dropped after repeated IAM
# token / webhook-path drift issues. drive-watcher.gs is no longer used.
#
# Actual billing (Jul 2026, db-custom-1-3840 tier): Cloud SQL ~$46/mo, Cloud
# Run ~$17/mo, Artifact Registry/Secret Manager ~$2/mo — real total ~$65/mo,
# well under the old ~$90-100/mo public-pricing estimate. Cloud SQL is the
# dominant line (~70%) despite this being pure control-plane data (n8n's own
# workflows/creds/execution history — no deal/business data ever touches this
# instance, see pipeline/app.py for where Attio dedup actually happens). Switched
# to db-f1-micro (~$9/mo quoted in console) since shared-core is fully
# sufficient for that workload as long as execution history is pruned (see
# EXECUTIONS_DATA_PRUNE below) — new estimated total ~$28/mo.
#
# Prereqs:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - Billing enabled on the project
#
# Usage:
#   chmod +x deploy.sh && ./deploy.sh
#
set -euo pipefail

# ─────────────────────────── CONFIG ────────────────────────────
PROJECT_ID="molten-crowbar-498920-q8"   # GCP project (same as your Flask app)
REGION="us-east4"                        # match your existing Cloud Run service
SERVICE="n8n"
AR_REPO="n8n"                            # Artifact Registry repo name
IMAGE_TAG="2.28.4"                       # keep in sync with the Dockerfile FROM tag

SQL_INSTANCE="n8n-db"
SQL_TIER="db-f1-micro"                   # shared-core, 1 vCPU / 0.614GB — n8n only stores
                                          # its own control-plane data here (workflows,
                                          # creds, execution history), never business data,
                                          # so shared-core is fine as long as execution
                                          # history stays pruned (see EXECUTIONS_DATA_PRUNE
                                          # below). No SLA / no CUD eligibility on shared-core,
                                          # irrelevant for this internal tool. If it ever
                                          # throttles or runs low on memory, bump to
                                          # db-g1-small (1.7GB, ~$24/mo) — a one-line change.
SQL_DB_NAME="n8n"
SQL_DB_USER="n8n"

# n8n only receives native Drive/Sheets polling triggers now (see header note
# above) — nothing external needs to reach it. So instead of exposing it
# publicly and relying on n8n's own login, Cloud Run is kept private
# (--no-allow-unauthenticated) and gated by IAP: only the Google accounts
# listed here can open the editor URL at all (Google sign-in happens before
# the request even reaches n8n). Space-separated; add teammates here and
# re-run this script to grant them access.
ALLOWED_IAP_USERS="oscar@id8investments.com"

# n8n encryption key — generated once and stored in Secret Manager.
# If migrating from local n8n, set this to the key from ~/.n8n/config
# ("encryptionKey") so saved credentials don't need to be re-entered. In this
# migration every credential is OAuth (Drive/Gmail/Sheets) and needs
# re-authorization against the new URL regardless, so a fresh key is fine.
N8N_ENCRYPTION_KEY="${N8N_ENCRYPTION_KEY:-$(openssl rand -hex 24)}"
# ────────────────────────────────────────────────────────────────

gcloud config set project "$PROJECT_ID"

echo "==> Enabling required APIs"
REQUIRED_APIS="run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com iap.googleapis.com"
ALREADY_ENABLED=$(gcloud services list --enabled --format="value(config.name)" \
  --filter="$(echo $REQUIRED_APIS | sed 's/ / OR name:/g;s/^/name:/')" 2>/dev/null | wc -l | tr -d ' ')
if [ "$ALREADY_ENABLED" -eq 6 ]; then
  echo "All required APIs already enabled — skipping (avoids the serviceusage.googleapis.com mutate-request quota)."
else
  gcloud services enable $REQUIRED_APIS
fi

echo "==> Creating Artifact Registry repo (if missing)"
gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1 || \
gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker --location="$REGION" \
  --description="n8n images"

echo "==> Creating Cloud SQL Postgres instance (if missing) — this takes 5-10 min the first time"
if ! gcloud sql instances describe "$SQL_INSTANCE" >/dev/null 2>&1; then
  gcloud sql instances create "$SQL_INSTANCE" \
    --database-version=POSTGRES_16 \
    --edition=ENTERPRISE \
    --tier="$SQL_TIER" \
    --region="$REGION" \
    --storage-size=10GB \
    --storage-auto-increase
fi

CONNECTION_NAME=$(gcloud sql instances describe "$SQL_INSTANCE" --format="value(connectionName)")
echo "==> Cloud SQL connection name: $CONNECTION_NAME"

echo "==> Creating database + user (if missing)"
gcloud sql databases describe "$SQL_DB_NAME" --instance="$SQL_INSTANCE" >/dev/null 2>&1 || \
gcloud sql databases create "$SQL_DB_NAME" --instance="$SQL_INSTANCE"

DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 20)}"
if gcloud sql users list --instance="$SQL_INSTANCE" --format="value(name)" | grep -qx "$SQL_DB_USER"; then
  gcloud sql users set-password "$SQL_DB_USER" --instance="$SQL_INSTANCE" --password="$DB_PASSWORD"
else
  gcloud sql users create "$SQL_DB_USER" --instance="$SQL_INSTANCE" --password="$DB_PASSWORD"
fi

# Update Secret Manager IMMEDIATELY after the real DB password changes — not
# after the build. A failed build (rate limits, registry hiccups, etc.) used
# to abort the script here via `set -e` before this ran, leaving the real
# Cloud SQL password and Secret Manager permanently out of sync, causing
# n8n's next cold start to fail with "password authentication failed".
echo "==> Storing secrets in Secret Manager"
upsert_secret () {
  local name="$1" val="$2"
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    printf '%s' "$val" | gcloud secrets versions add "$name" --data-file=-
  else
    printf '%s' "$val" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic
  fi
}
upsert_secret n8n-encryption-key "$N8N_ENCRYPTION_KEY"
upsert_secret n8n-db-password    "$DB_PASSWORD"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/n8n:${IMAGE_TAG}"

echo "==> Building & pushing image with Cloud Build"
gcloud builds submit --config=cloudbuild.yaml --substitutions=_IMAGE="$IMAGE" .

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for s in n8n-encryption-key n8n-db-password; do
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
done

echo "==> Granting Cloud SQL Client role to the runtime service account"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/cloudsql.client" >/dev/null

echo "==> Deploying to Cloud Run"
# Flags:
#   --min-instances=1  : always warm — required for n8n's native Drive/Sheets
#     Trigger nodes to poll on their own schedule. (Was 0/scale-to-zero back
#     when triggers were external webhooks; no longer applies.)
#   --max-instances=1  : n8n regular mode requires a single instance.
#   --add-cloudsql-instances: mounts the Cloud SQL Unix socket at /cloudsql/<connection-name>.
#   --no-cpu-throttling: without this, CPU is throttled except while actively
#     handling a request. Originally added because n8n 2.x's DB
#     connection-monitor/ping background work during boot was getting
#     CPU-starved, causing spurious "Database ping failed" errors. Now also
#     required so the Drive/Sheets Trigger polling loop isn't starved between
#     requests. Costs meaningfully more since the instance is always on
#     (see cost estimate above); worth it for reliability.
#   --no-allow-unauthenticated --iap: nothing external needs to reach this
#     service (see ALLOWED_IAP_USERS above) — Cloud Run stays private and IAP
#     gates every request behind Google sign-in before it hits n8n at all.
#     Previously this was --allow-unauthenticated (fully public, relying on
#     n8n's own login page as the only gate) — fixed 2026-07-14 audit.
#
# WEBHOOK_URL is still set for n8n's internal callback/editor URLs (OAuth
# redirects, editor base URL) even though nothing external POSTs to it anymore.
# Deploy once with a placeholder, capture the real URL, then re-deploy with it
# set so those URLs resolve correctly.
#
# EXECUTIONS_DATA_PRUNE=true (+ MAX_AGE/PRUNE_MAX_COUNT): without this, n8n
# keeps every execution record forever. Cloud SQL storage only grows, never
# shrinks, without recreating the instance — so unbounded execution history is
# a one-way cost ratchet, and on db-f1-micro's 0.614GB it also eats the memory
# headroom the shared-core tier needs to stay stable. Keeps 14 days / 10k rows,
# whichever is smaller.

deploy () {
  local webhook_url="$1"
  gcloud run deploy "$SERVICE" \
    --image="$IMAGE" \
    --region="$REGION" \
    --platform=managed \
    --no-allow-unauthenticated \
    --iap \
    --port=5678 \
    --cpu=1 \
    --memory=1Gi \
    --min-instances=1 \
    --max-instances=1 \
    --timeout=3600 \
    --no-cpu-throttling \
    --add-cloudsql-instances="$CONNECTION_NAME" \
    --set-env-vars="^@@^N8N_PORT=5678@@N8N_PROTOCOL=https@@N8N_HOST=${webhook_url#https://}@@N8N_EDITOR_BASE_URL=${webhook_url}@@WEBHOOK_URL=${webhook_url}@@GENERIC_TIMEZONE=America/New_York@@N8N_RUNNERS_ENABLED=false@@N8N_DIAGNOSTICS_ENABLED=false@@N8N_ENDPOINT_HEALTH=health@@N8N_RUNNERS_GRANT_TOKEN_TTL=120000@@DB_TYPE=postgresdb@@DB_POSTGRESDB_HOST=/cloudsql/${CONNECTION_NAME}@@DB_POSTGRESDB_DATABASE=${SQL_DB_NAME}@@DB_POSTGRESDB_USER=${SQL_DB_USER}@@EXECUTIONS_DATA_PRUNE=true@@EXECUTIONS_DATA_MAX_AGE=336@@EXECUTIONS_DATA_PRUNE_MAX_COUNT=10000" \
    --set-secrets="N8N_ENCRYPTION_KEY=n8n-encryption-key:latest,DB_POSTGRESDB_PASSWORD=n8n-db-password:latest"
}

deploy "https://placeholder.invalid"
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format="value(status.url)")
echo "==> Service URL: $URL — re-deploying with WEBHOOK_URL set"
deploy "$URL"

echo "==> Wiring up IAP access"
# The IAP service agent needs run.invoker on the service itself — this is how
# a request that already passed IAP's Google-sign-in check is allowed through
# to n8n. Without this binding, IAP would authenticate the user and then
# Cloud Run would still reject the request.
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" \
  --role="roles/run.invoker" >/dev/null

# Separately, each individual human who should be able to open the app at all
# needs iap.httpsResourceAccessor — this is the actual allowlist.
for user in $ALLOWED_IAP_USERS; do
  gcloud iap web add-iam-policy-binding \
    --member="user:${user}" \
    --role="roles/iap.httpsResourceAccessor" \
    --region="$REGION" \
    --resource-type=cloud-run \
    --service="$SERVICE" >/dev/null
done

cat <<EOF

────────────────────────────────────────────────────────────
 Done. n8n is live at: $URL
────────────────────────────────────────────────────────────
 SAVE THESE — needed if you ever redeploy or migrate:
   N8N_ENCRYPTION_KEY = $N8N_ENCRYPTION_KEY
   DB_PASSWORD         = $DB_PASSWORD
   (both also stored in Secret Manager)

 Estimated cost: ~\$28/mo (based on actual Jul 2026 billing, not public pricing)
   - Cloud SQL: $SQL_TIER, always-on, ~\$9/mo — execution history is pruned
     (EXECUTIONS_DATA_PRUNE, 14 days / 10k rows) to keep it living within
     shared-core's memory headroom long-term
   - Cloud Run: min=1, always warm, --no-cpu-throttling, ~\$17/mo
   - Artifact Registry + Secret Manager: ~\$2/mo
   - IAP: no additional cost

 ACCESS: $URL is now private — only these Google accounts can open it at all
 (IAP prompts for Google sign-in before the request ever reaches n8n):
   $ALLOWED_IAP_USERS
 To add someone, add their email to ALLOWED_IAP_USERS at the top of this
 script and re-run it (safe/idempotent — won't recreate existing infra).

 NEXT STEPS:
 1. Open $URL, sign in with an allowed Google account, then create your n8n
    owner account (skip if already provisioned).
 2. Google Cloud Console → APIs & Services → Credentials → create/edit your
    OAuth client for Drive/Gmail/Sheets → add Authorized redirect URI:
      ${URL}/rest/oauth2-credential/callback
 3. Re-authenticate Google Drive, Gmail, and Google Sheets credentials inside n8n.
 4. In the "ID8 PB-Attio" workflow, confirm each Google Drive Trigger node's
    folder ID and poll interval, and fix any flagged (red-warning) nodes —
    usually a stale credential.
 5. Activate the workflow and confirm runs show up in the Executions tab.
 6. drive-watcher.gs / Apps Script is no longer needed — safe to delete its
    triggers (or the whole script project) once step 5 is confirmed working.
────────────────────────────────────────────────────────────
EOF
