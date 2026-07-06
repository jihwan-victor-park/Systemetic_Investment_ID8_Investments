#!/usr/bin/env bash
# Deploy the Attio → Constant Contact list-sync webhook to Cloud Run.
# Run from this directory: ./deploy.sh
#
# Prerequisite: ./setup_secrets.sh has been run once already (creates the 4
# secrets and grants this service's runtime service account access to them).
# See README.md for the full one-time setup order.
set -euo pipefail

PROJECT="${PROJECT:-137750788450}"
REGION="${REGION:-us-east4}"   # same project/region as the rest of this repo's Cloud Run services
SERVICE="cc-attio-sync"

# Attio list key -> Constant Contact list UUID. Get UUIDs by running
# `python list_cc_lists.py` (after setup_secrets.sh) or from the CC list URL.
# Edit this before your first real deploy.
CC_LIST_MAP='{"newsletter":"REPLACE_WITH_CC_LIST_UUID"}'

if [[ "$CC_LIST_MAP" == *"REPLACE_WITH_CC_LIST_UUID"* ]]; then
  echo "CC_LIST_MAP in deploy.sh still has the placeholder UUID." >&2
  echo "Run 'python list_cc_lists.py' and paste the real mapping in, then re-run." >&2
  exit 1
fi

gcloud run deploy "$SERVICE" \
  --source . \
  --project="$PROJECT" \
  --region="$REGION" \
  --allow-unauthenticated \
  --max-instances=1 \
  --set-env-vars="CC_LIST_MAP=$CC_LIST_MAP" \
  --set-secrets="CC_CLIENT_ID=CC_CLIENT_ID:latest,CC_CLIENT_SECRET=CC_CLIENT_SECRET:latest,CC_REFRESH_TOKEN=CC_REFRESH_TOKEN:latest,WEBHOOK_SECRET=WEBHOOK_SECRET:latest"

echo
echo "Webhook URL:  $(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT" --format='value(status.url)')/attio-webhook"
