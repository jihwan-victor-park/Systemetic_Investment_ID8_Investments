#!/usr/bin/env bash
#
# Provisions the API Gateway that fronts the private cc-attio-sync Cloud Run
# service (see openapi.yaml's description for why a Gateway exists at all --
# short version: org policy blocks public Cloud Run, so `--allow-unauthenticated`
# on deploy.sh doesn't actually make the service reachable).
#
# This reconstructs the setup originally done by hand in Cloud Shell on
# 2026-07-13 (see project memory project_cc_attio_sync_public_access_fix) --
# it was never checked into the repo until now. Idempotent (every gcloud call
# below checks for the existing resource first), but re-verify against live
# state with `gcloud api-gateway gateways describe "$GATEWAY" --location="$REGION"`
# before trusting this script blindly if it's been a while since it last ran.
#
# Prerequisite: cc-attio-sync's own ./deploy.sh has already deployed the
# Cloud Run service at least once.
#
# Usage: run from this directory: ./deploy-gateway.sh
set -euo pipefail

PROJECT="${PROJECT:-molten-crowbar-498920-q8}"
REGION="${REGION:-us-east4}"           # same region as the Cloud Run service
SERVICE="${SERVICE:-cc-attio-sync}"    # the backend Cloud Run service
API="${API:-cc-attio-sync-api}"
GATEWAY="${GATEWAY:-cc-attio-sync-gw}"
CONFIG_VERSION="${CONFIG_VERSION:-v$(date +%s)}"   # unique per deploy -- API Gateway configs are immutable once created
INVOKER_SA_NAME="cc-attio-gateway-invoker"
INVOKER_SA="${INVOKER_SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT" >/dev/null

echo "==> Enabling required APIs"
gcloud services enable apigateway.googleapis.com servicemanagement.googleapis.com servicecontrol.googleapis.com run.googleapis.com

echo "==> Force-provisioning API Gateway's service identity (enabling the API alone does not create it)"
gcloud beta services identity create --service=apigateway.googleapis.com --project="$PROJECT" >/dev/null 2>&1 || true
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")
APIGATEWAY_SA="service-${PROJECT_NUMBER}@gcp-sa-apigateway.iam.gserviceaccount.com"

echo "==> Creating the dedicated backend-invoker service account (if missing)"
gcloud iam service-accounts describe "$INVOKER_SA" >/dev/null 2>&1 || \
gcloud iam service-accounts create "$INVOKER_SA_NAME" \
  --display-name="cc-attio-sync API Gateway backend invoker"

echo "==> Granting the invoker SA run.invoker on $SERVICE"
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${INVOKER_SA}" \
  --role="roles/run.invoker" >/dev/null

echo "==> Letting API Gateway's own service agent mint tokens as the invoker SA"
gcloud iam service-accounts add-iam-policy-binding "$INVOKER_SA" \
  --member="serviceAccount:${APIGATEWAY_SA}" \
  --role="roles/iam.serviceAccountTokenCreator" >/dev/null

echo "==> Looking up the live Cloud Run URL"
BACKEND_URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')
echo "    $BACKEND_URL"

TMP_SPEC="$(mktemp)"
trap 'rm -f "$TMP_SPEC"' EXIT
sed "s|https://REPLACE_WITH_CLOUD_RUN_URL|${BACKEND_URL}|" openapi.yaml > "$TMP_SPEC"

echo "==> Creating the API (if missing)"
gcloud api-gateway apis describe "$API" >/dev/null 2>&1 || \
gcloud api-gateway apis create "$API"

echo "==> Creating a new API config ($CONFIG_VERSION) from openapi.yaml -- configs are immutable, each deploy makes a new one"
gcloud api-gateway api-configs create "$CONFIG_VERSION" \
  --api="$API" \
  --openapi-spec="$TMP_SPEC" \
  --backend-auth-service-account="$INVOKER_SA"

echo "==> Pointing the gateway at the new config (creates the gateway on first run)"
if gcloud api-gateway gateways describe "$GATEWAY" --location="$REGION" >/dev/null 2>&1; then
  gcloud api-gateway gateways update "$GATEWAY" \
    --api="$API" --api-config="$CONFIG_VERSION" --location="$REGION"
else
  gcloud api-gateway gateways create "$GATEWAY" \
    --api="$API" --api-config="$CONFIG_VERSION" --location="$REGION"
fi

GATEWAY_HOST=$(gcloud api-gateway gateways describe "$GATEWAY" --location="$REGION" --format='value(defaultHostname)')
cat <<EOF

────────────────────────────────────────────────────────────
 Done. Public webhook base URL: https://${GATEWAY_HOST}
   Health check:        https://${GATEWAY_HOST}/health
   Attio add webhook:    https://${GATEWAY_HOST}/attio-webhook
   Attio delete webhook: https://${GATEWAY_HOST}/attio-delete-webhook

 Point Attio's automations at these URLs (Oscar does this by hand in the
 Attio UI -- not scriptable). /reconcile is intentionally NOT exposed here;
 it's called by Cloud Scheduler directly against the private Cloud Run URL.
────────────────────────────────────────────────────────────
EOF
