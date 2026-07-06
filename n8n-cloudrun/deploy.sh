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
# Estimated cost: ~$25-35/mo (Cloud SQL db-custom-1-3840) + ~$60-70/mo for
# Cloud Run kept always-on (min-instances=1, --no-cpu-throttling — required
# so the Drive Trigger's background poll isn't CPU-starved between requests).
# Total ~$90-100/mo. Check the GCP pricing calculator / actual billing for
# a precise number; this is a rough estimate.
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
SQL_TIER="db-custom-1-3840"              # 1 vCPU / 3.75GB — smallest comfortable tier
SQL_DB_NAME="n8n"
SQL_DB_USER="n8n"

# n8n encryption key — generated once and stored in Secret Manager.
# If migrating from local n8n, set this to the key from ~/.n8n/config
# ("encryptionKey") so saved credentials don't need to be re-entered. In this
# migration every credential is OAuth (Drive/Gmail/Sheets) and needs
# re-authorization against the new URL regardless, so a fresh key is fine.
N8N_ENCRYPTION_KEY="${N8N_ENCRYPTION_KEY:-$(openssl rand -hex 24)}"
# ────────────────────────────────────────────────────────────────

gcloud config set project "$PROJECT_ID"

echo "==> Enabling required APIs"
REQUIRED_APIS="run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com"
ALREADY_ENABLED=$(gcloud services list --enabled --format="value(config.name)" \
  --filter="$(echo $REQUIRED_APIS | sed 's/ / OR name:/g;s/^/name:/')" 2>/dev/null | wc -l | tr -d ' ')
if [ "$ALREADY_ENABLED" -eq 5 ]; then
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
#
# WEBHOOK_URL is still set for n8n's internal callback/editor URLs (OAuth
# redirects, editor base URL) even though nothing external POSTs to it anymore.
# Deploy once with a placeholder, capture the real URL, then re-deploy with it
# set so those URLs resolve correctly.

deploy () {
  local webhook_url="$1"
  gcloud run deploy "$SERVICE" \
    --image="$IMAGE" \
    --region="$REGION" \
    --platform=managed \
    --allow-unauthenticated \
    --port=5678 \
    --cpu=1 \
    --memory=1Gi \
    --min-instances=1 \
    --max-instances=1 \
    --timeout=3600 \
    --no-cpu-throttling \
    --add-cloudsql-instances="$CONNECTION_NAME" \
    --set-env-vars="^@@^N8N_PORT=5678@@N8N_PROTOCOL=https@@N8N_HOST=${webhook_url#https://}@@N8N_EDITOR_BASE_URL=${webhook_url}@@WEBHOOK_URL=${webhook_url}@@GENERIC_TIMEZONE=America/New_York@@N8N_RUNNERS_ENABLED=false@@N8N_DIAGNOSTICS_ENABLED=false@@N8N_ENDPOINT_HEALTH=health@@N8N_RUNNERS_GRANT_TOKEN_TTL=120000@@DB_TYPE=postgresdb@@DB_POSTGRESDB_HOST=/cloudsql/${CONNECTION_NAME}@@DB_POSTGRESDB_DATABASE=${SQL_DB_NAME}@@DB_POSTGRESDB_USER=${SQL_DB_USER}" \
    --set-secrets="N8N_ENCRYPTION_KEY=n8n-encryption-key:latest,DB_POSTGRESDB_PASSWORD=n8n-db-password:latest"
}

deploy "https://placeholder.invalid"
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format="value(status.url)")
echo "==> Service URL: $URL — re-deploying with WEBHOOK_URL set"
deploy "$URL"

cat <<EOF

────────────────────────────────────────────────────────────
 Done. n8n is live at: $URL
────────────────────────────────────────────────────────────
 SAVE THESE — needed if you ever redeploy or migrate:
   N8N_ENCRYPTION_KEY = $N8N_ENCRYPTION_KEY
   DB_PASSWORD         = $DB_PASSWORD
   (both also stored in Secret Manager)

 Estimated cost: ~\$90-100/mo (rough — verify against actual billing)
   - Cloud SQL: $SQL_TIER, always-on
   - Cloud Run: min=1, always warm, --no-cpu-throttling — the new cost driver
     now that triggers are native polling nodes instead of webhooks
   - Artifact Registry + Secret Manager: negligible

 NEXT STEPS:
 1. Open $URL and create your owner account (skip if already provisioned).
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
