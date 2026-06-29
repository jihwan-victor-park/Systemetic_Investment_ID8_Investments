#!/usr/bin/env bash
#
# Deploy self-hosted n8n to Google Cloud Run, backed by Neon serverless Postgres.
# Total cost: ~$1-3/mo (Cloud Run scales to zero between webhook events; Neon is free).
#
# Prereqs:
#   - gcloud CLI installed and authenticated  (gcloud auth login)
#   - Docker running locally
#   - Billing enabled on the project
#   - A free Neon account at https://neon.tech — create a project, copy the
#     connection string (looks like postgres://user:pass@host/dbname?sslmode=require)
#     and set it as NEON_DATABASE_URL below or in your environment.
#
# Usage:
#   1. Edit the CONFIG block below.
#   2. export NEON_DATABASE_URL="postgres://..."   # from neon.tech dashboard
#   3. chmod +x deploy.sh && ./deploy.sh
#
set -euo pipefail

# ─────────────────────────── CONFIG ────────────────────────────
PROJECT_ID="id8-investments"   # GCP project (same as your Flask app)
REGION="us-east4"              # match your existing Cloud Run service
SERVICE="n8n"
AR_REPO="n8n"                  # Artifact Registry repo name
IMAGE_TAG="1.108.2"            # keep in sync with the Dockerfile FROM tag

# Neon connection string — set via env or paste here.
# Get it from: neon.tech → your project → Connection Details → Connection string
NEON_DATABASE_URL="${NEON_DATABASE_URL:?Set NEON_DATABASE_URL to your Neon connection string}"

# n8n encryption key — generated once and stored in Secret Manager.
# If migrating from local n8n, set this to the key from ~/.n8n/config
# ("encryptionKey") so saved credentials don't need to be re-entered.
N8N_ENCRYPTION_KEY="${N8N_ENCRYPTION_KEY:-$(openssl rand -hex 24)}"
# ────────────────────────────────────────────────────────────────

gcloud config set project "$PROJECT_ID"

echo "==> Enabling required APIs"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com

echo "==> Creating Artifact Registry repo (if missing)"
gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1 || \
gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker --location="$REGION" \
  --description="n8n images"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/n8n:${IMAGE_TAG}"

echo "==> Building & pushing image with Cloud Build"
gcloud builds submit --tag "$IMAGE" .

echo "==> Storing secrets in Secret Manager"
upsert_secret () {
  local name="$1" val="$2"
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    printf '%s' "$val" | gcloud secrets versions add "$name" --data-file=-
  else
    printf '%s' "$val" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic
  fi
}
upsert_secret n8n-encryption-key  "$N8N_ENCRYPTION_KEY"
upsert_secret n8n-database-url    "$NEON_DATABASE_URL"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for s in n8n-encryption-key n8n-database-url; do
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
done

echo "==> Deploying to Cloud Run"
# Cost-saving flags:
#   --min-instances=0  : scale to zero when idle — n8n only runs during webhook events (~weekly).
#   --max-instances=1  : single instance required; n8n regular mode isn't multi-instance safe.
#   --cpu-throttling   : (default, no flag needed) CPU only allocated during requests — cheapest tier.
#   --memory=1Gi       : n8n's Node.js process needs ~600-800MB headroom on startup; 512MB OOMs.
#
# No --add-cloudsql-instances needed — Neon connects over TLS like any external Postgres.
#
# WEBHOOK_URL must be the public URL. Deploy once with a placeholder, capture the real
# URL, then re-deploy with it set so OAuth callbacks and webhook paths resolve correctly.

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
    --set-env-vars="^@@^N8N_PORT=5678@@N8N_PROTOCOL=https@@N8N_HOST=${webhook_url#https://}@@N8N_EDITOR_BASE_URL=${webhook_url}@@WEBHOOK_URL=${webhook_url}@@GENERIC_TIMEZONE=America/New_York@@N8N_RUNNERS_ENABLED=true@@N8N_DIAGNOSTICS_ENABLED=false@@DB_TYPE=postgresdb" \
    --set-secrets="N8N_ENCRYPTION_KEY=n8n-encryption-key:latest,DB_POSTGRESDB_URL=n8n-database-url:latest"
}

deploy "https://placeholder.invalid"
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format="value(status.url)")
echo "==> Service URL: $URL — re-deploying with WEBHOOK_URL set"
deploy "$URL"

cat <<EOF

────────────────────────────────────────────────────────────
 Done. n8n is live at: $URL
────────────────────────────────────────────────────────────
 SAVE THIS — needed if you ever redeploy or migrate:
   N8N_ENCRYPTION_KEY = $N8N_ENCRYPTION_KEY
   (also stored in Secret Manager as 'n8n-encryption-key')

 Estimated cost: ~\$8-12/mo
   - Cloud Run: min=1 always-on instance, CPU throttled when idle (~\$8-10/mo)
   - Neon Postgres: free tier (0.5GB storage, plenty for n8n)
   - Secret Manager: negligible (<\$0.10/mo)

 NEXT STEPS:
 1. Open $URL and create your owner account.
 2. Google Cloud Console → APIs & Services → Credentials → edit your
    OAuth client → add Authorized redirect URI:
      ${URL}/rest/oauth2-credential/callback
 3. Re-authenticate Google Drive + Gmail credentials inside n8n.
 4. Import n8n-cloudrun/ID8_PB-Attio_webhook.json into n8n.
 5. Activate the workflow — copy the 4 Production webhook URLs.
 6. Paste those URLs into drive-watcher.gs (N8N_BASE), deploy to
    Apps Script, run installTriggers() once.
────────────────────────────────────────────────────────────
EOF
