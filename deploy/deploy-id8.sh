#!/usr/bin/env bash
# Deploy the Flask backend (`id8`) to Cloud Run.
#
# WHY THIS FILE EXISTS
# --------------------
# Production deploys happen automatically: Cloud Build trigger
# 0ed43e8f-663f-48b6-af45-18513c562fbd watches ocachin/id8-intelligence@main,
# builds this repo's root Dockerfile, and runs `gcloud run services update id8
# --image=...`. That deploy step swaps ONLY the image -- it never sets env vars,
# secrets, memory, or scaling. So every one of those settings has existed
# nowhere but in the live service since 2026-06-22, and deleting the service
# would have destroyed the only copy.
#
# This script is that copy. Values below were captured from the live service on
# 2026-08-26 (revision id8-00338-5px, generation 339, commit 6085a8b) and match
# it exactly. It is a RECOVERY + REVIEW artifact first and a deploy tool second:
# the normal path stays the Cloud Build trigger.
#
#   ./deploy/deploy-id8.sh --dry-run   # print the command, change nothing
#   ./deploy/deploy-id8.sh             # apply config (prompts first)
#
# Secrets are referenced by Secret Manager name only. No secret value appears
# in this file, and none should ever be added to it.
set -euo pipefail

PROJECT="${PROJECT:-molten-crowbar-498920-q8}"
REGION="${REGION:-us-east4}"
SERVICE="${SERVICE:-id8}"

# The default Compute SA. Carried over from the original deploy, NOT endorsed --
# see deploy/PRODUCTION_CONFIG.md "Service account" for why this should become a
# dedicated runtime account, and why that change needs its own rollback plan.
RUNTIME_SA="${RUNTIME_SA:-137750788450-compute@developer.gserviceaccount.com}"

# --- Resources -------------------------------------------------------------
# memory 2Gi: raised at some point after the root Dockerfile's comment was
#   written. That comment still describes a 512 MiB limit and the 2026-08-03
#   OOM; it is STALE as a description of production. The `--workers 1` decision
#   it also justifies remains correct for the OTHER reason it gives (module-level
#   _pipeline_state must live in one process), so do not "fix" the worker count
#   just because the memory pressure is gone.
# no-cpu-throttling: CPU stays allocated outside requests, so the background
#   pipeline thread keeps running after _start_pipeline returns.
# timeout 1800: MUST match the root Dockerfile's gunicorn --timeout. Cloud Run's
#   request timeout would otherwise cut the connection before gunicorn's does.
MEMORY="2Gi"
CPU="1000m"
TIMEOUT="1800"
CONCURRENCY="80"

# max-instances 3: this is the live value and is reproduced faithfully, but see
# deploy/PRODUCTION_CONFIG.md "Known risk: max-instances vs the intake lock" --
# _pipeline_slot is a per-PROCESS semaphore, so it cannot serialize intake runs
# across instances, and /process/status can land on an instance that knows
# nothing about the run. Changing this to 1 is a behavior decision, not a
# cleanup; it is deliberately NOT changed here.
MAX_INSTANCES="3"

# --- Plain env vars --------------------------------------------------------
DI_HUB_BASE_URL="https://molten-crowbar-498920-q8.web.app"
DI_DOCX_BUCKET="molten-crowbar-498920-q8-hub-next-docs"

# --- Secret Manager bindings (NAMES ONLY) ----------------------------------
# Format: ENV_VAR=secret-name:version
SECRETS="PERPLEXITY_API_KEY=PERPLEXITY_API_KEY:latest"
SECRETS="${SECRETS},ATTIO_API_KEY=ATTIO_API_KEY:latest"
SECRETS="${SECRETS},GH_TOKEN=GH_TOKEN:latest"
SECRETS="${SECRETS},ATTIO_WEBHOOK_SECRET=id8-attio-webhook-secret:latest"

# NOT currently bound on the live service. Each is read by code that silently
# degrades rather than failing loudly, which is why their absence went unnoticed:
#   ANTHROPIC_API_KEY  -- Stage 2 memo synthesis + rubric scoring (config.py).
#                         Also missing from deal_intelligence/_secrets.py's map,
#                         so Secret Manager cannot supply it either way.
#   APOLLO_API_KEY     -- Radar headcount enrichment (apollo_org.py). Without it
#                         capital_clock has no burn-rate input.
#   OPENAI_API_KEY     -- embeddings for portfolio_prefilter only.
#   INTERNAL_API_SECRET-- gates hub-next -> pipeline. Unset means
#                         _require_internal_secret() returns True for everyone,
#                         i.e. every route on this public service is open.
# Uncomment a line only after the secret exists AND the runtime SA can read it.
#SECRETS="${SECRETS},ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest"
#SECRETS="${SECRETS},APOLLO_API_KEY=APOLLO_API_KEY:latest"
#SECRETS="${SECRETS},OPENAI_API_KEY=OPENAI_API_KEY:latest"
#SECRETS="${SECRETS},INTERNAL_API_SECRET=id8-internal-api-secret:latest"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

cmd=(gcloud run services update "$SERVICE"
  --project="$PROJECT"
  --region="$REGION"
  --service-account="$RUNTIME_SA"
  --memory="$MEMORY"
  --cpu="$CPU"
  --no-cpu-throttling
  --timeout="$TIMEOUT"
  --concurrency="$CONCURRENCY"
  --max-instances="$MAX_INSTANCES"
  --ingress=all
  --update-env-vars="DI_HUB_BASE_URL=${DI_HUB_BASE_URL},DI_DOCX_BUCKET=${DI_DOCX_BUCKET}"
  --update-secrets="$SECRETS")

echo "# Target: ${SERVICE} in ${PROJECT}/${REGION}"
printf '%q ' "${cmd[@]}"; echo

if [[ $DRY_RUN -eq 1 ]]; then
  echo "# --dry-run: nothing applied."
  exit 0
fi

echo
echo "Current revision (record this for rollback):"
gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" \
  --format='value(status.latestReadyRevisionName)'
echo
read -r -p "Apply the above to PRODUCTION? [y/N] " reply
[[ "$reply" == "y" || "$reply" == "Y" ]] || { echo "Aborted."; exit 1; }
"${cmd[@]}"

cat <<'ROLLBACK'

Rollback (substitute the revision name printed above):
  gcloud run services update-traffic id8 \
    --project=molten-crowbar-498920-q8 --region=us-east4 \
    --to-revisions=<REVISION_NAME>=100
ROLLBACK
