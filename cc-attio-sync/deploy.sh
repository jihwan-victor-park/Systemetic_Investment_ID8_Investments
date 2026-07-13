#!/usr/bin/env bash
# Deploy the Attio → Constant Contact list-sync webhook to Cloud Run.
# Run from this directory: ./deploy.sh
#
# Prerequisite: ./setup_secrets.sh has been run once already (creates the 4
# secrets and grants this service's runtime service account access to them).
# See README.md for the full one-time setup order.
set -euo pipefail

PROJECT="${PROJECT:-molten-crowbar-498920-q8}"   # gcloud run deploy requires the project ID, not the number
REGION="${REGION:-us-east4}"   # same project/region as the rest of this repo's Cloud Run services
SERVICE="cc-attio-sync"

# Attio list key -> Constant Contact list UUID. Get UUIDs by running
# `python list_cc_lists.py` (after setup_secrets.sh) or from the CC list URL.
# Edit this before your first real deploy.
CC_LIST_MAP='{"polymarket-reminder-list":"00ccbbe6-4337-11f1-8fb6-02420a320002","higgsfield-reachout-list":"0f8230f8-7433-11f1-90f8-02420a320003","higgsfield-additional-people":"1cca3d8c-7596-11f1-a010-02420a320002","harvey-dinner-list":"2894f0e4-6033-11f1-9bb0-02420a320003","monthly-update-contact-list":"32c353b8-ba92-11f0-8997-0242f4571009","base-power-spv-investors":"373c9caa-7965-11f1-967c-02420a320002","id8-investors":"5a36cb72-0e81-11f0-8c22-fa163e696719","new-deal-list":"67ca62f4-eed7-11ef-a2b2-fa163e559d5a","fund-second-close-list":"6ae8afd4-6070-11f1-9915-02420a320003","reflection-ai-spv-investors":"7c8de712-7967-11f1-846a-02420a320003","polymarket":"80ee3c48-2602-11f1-a51a-0242f57f1695","replit-potential-investors":"928175a0-f656-11f0-a430-02429ee7b686","portfolio-news-list":"9afb7aee-4645-11f0-b80b-fa163e696719","synchron-investors":"9c5fa4b4-0f31-11f0-89f5-fa163e696719","dougs-list":"a7743b9e-4645-11f0-9ef7-fa163ea76f79","did-not-open":"ac3270ce-f306-11f0-a082-024273a36381","replit-follow-on":"bb741972-4d86-11f1-ad2c-02420a320002","sofias-list":"bbf45558-4646-11f0-b6ed-fa163e6d2858","id8-fund-and-spv-investors-2025":"d565c962-2e13-11f1-9c48-02420a320002","kudo-investors":"d56f0bf8-6ff9-11f1-93e8-02420a320002","scale-spv-investors":"d7ad7c54-7965-11f1-a2da-02420a320002","fund-investors":"dab49346-cae8-11f0-a8dc-02429ee7b686","together-ai-spv-investors":"dbd7241e-7952-11f1-8d4a-02420a320002","fund-announcement-list":"dd1a5ea4-be45-11f0-bf0f-0242f4571009","saronic-spv-investors":"e2136a72-7966-11f1-bb18-02420a320002","general-interest":"e5d756f8-bc7d-11ee-9061-fa163e638ddc","betterment-investors":"e982c1fc-6f13-11f1-bb2b-02420a320003","replit-spv-investors":"ee5dbf14-7969-11f1-9edd-02420a320002","quarterly-contacts-1q-2024":"f5ed54b8-0a4b-11ef-889b-fa163efab12a","polymarket-lps":"f8615fdc-3fe6-11f1-9bd2-02420a320002","groq-investors":"fc9500ca-5f8c-11f1-8630-02420a320003"}'

if [[ "$CC_LIST_MAP" == *"REPLACE_WITH_CC_LIST_UUID"* ]]; then
  echo "CC_LIST_MAP in deploy.sh still has the placeholder UUID." >&2
  echo "Run 'python list_cc_lists.py' and paste the real mapping in, then re-run." >&2
  exit 1
fi

# Attio list_id -> CC_LIST_MAP key, for /reconcile (see README "Reconciling
# removals"). Get list_ids by running `python list_attio_lists.py`. Empty by
# default -- /reconcile is a no-op until you fill this in.
ATTIO_LIST_MAP="${ATTIO_LIST_MAP:-{\}}"

gcloud run deploy "$SERVICE" \
  --source . \
  --project="$PROJECT" \
  --region="$REGION" \
  --allow-unauthenticated \
  --max-instances=1 \
  --set-env-vars="^@^CC_LIST_MAP=$CC_LIST_MAP@ATTIO_LIST_MAP=$ATTIO_LIST_MAP" \
  --set-secrets="CC_CLIENT_ID=CC_CLIENT_ID:latest,CC_CLIENT_SECRET=CC_CLIENT_SECRET:latest,CC_REFRESH_TOKEN=CC_REFRESH_TOKEN:latest,WEBHOOK_SECRET=WEBHOOK_SECRET:latest,ATTIO_API_KEY=ATTIO_API_KEY:latest"

echo
echo "Webhook URL:  $(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT" --format='value(status.url)')/attio-webhook"
