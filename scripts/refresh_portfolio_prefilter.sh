#!/usr/bin/env bash
# One command for the whole "recompute + persist + push" mechanic:
#
#   1. Runs deal_intelligence/portfolio_prefilter.py --all --persist, which
#      re-evaluates every company in every fund at/under --max-fund-size
#      (geography NA/Europe, business status, no-enrichment-data skip,
#      AI-relevance keyword+embeddings -- stage is deliberately NOT applied,
#      see that module's docstring) and stamps prefilterPass/prefilterReason
#      back onto hub-next/scripts/data/partner-vcs-seed.json.
#   2. Pushes that same seed file into Firestore via
#      hub-next/scripts/backfill-partner-vcs.mjs, so the hub's Portfolio
#      "Show all portfolio companies" toggle picks up the new verdicts.
#
# Local (dev emulator):
#   ./scripts/refresh_portfolio_prefilter.sh
#
# Real project (needs real gcloud/Application Default Credentials --
# not available in a sandboxed agent shell, run this from your own machine
# or Cloud Shell):
#   GCP_PROJECT_ID=<real-project-id> ./scripts/refresh_portfolio_prefilter.sh
#
# Optional passthrough:
#   MAX_FUND_SIZE=500 ./scripts/refresh_portfolio_prefilter.sh
#   USE_EMBEDDINGS=1 ./scripts/refresh_portfolio_prefilter.sh   (off by default --
#     the embeddings tier needs a funded OPENAI_API_KEY; the reported 2,724/3,778
#     result was produced keyword-only, so that stays the default rather than
#     silently attempting-and-falling-back per company against a key that's
#     out of quota)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAX_FUND_SIZE="${MAX_FUND_SIZE:-500}"
EMBEDDINGS_FLAG="--no-embeddings"
if [ "${USE_EMBEDDINGS:-0}" = "1" ]; then
  EMBEDDINGS_FLAG=""
fi

echo "== 1/2: recomputing prefilter + persisting to partner-vcs-seed.json =="
python3 -m deal_intelligence.portfolio_prefilter --all --persist --max-fund-size "$MAX_FUND_SIZE" \
  $EMBEDDINGS_FLAG --json > /tmp/portfolio_prefilter_summary.json
python3 -c "
import json
s = json.load(open('/tmp/portfolio_prefilter_summary.json'))
print(f\"  funds evaluated: {s['funds_evaluated']}  (deferred: {len(s['funds_deferred'])}, {s['companies_deferred']} companies)\")
print(f\"  companies evaluated: {s['companies_evaluated']}  pass: {s['companies_pass']}  excluded: {s['companies_excluded']}\")
for reason, n in sorted(s['exclude_reasons'].items(), key=lambda x: -x[1]):
    print(f'    {n:5d}  {reason}')
"

echo
if [ -n "${FIRESTORE_EMULATOR_HOST:-}" ]; then
  echo "== 2/2: pushing to Firestore emulator ($FIRESTORE_EMULATOR_HOST, project ${GCP_PROJECT_ID:-demo-hub-next}) =="
elif [ -n "${GCP_PROJECT_ID:-}" ]; then
  echo "== 2/2: pushing to REAL Firestore project $GCP_PROJECT_ID =="
else
  echo "!! Neither FIRESTORE_EMULATOR_HOST nor GCP_PROJECT_ID is set -- refusing to guess which"
  echo "!! Firestore project to push to. Set one and re-run (see usage comment at the top of this file)."
  exit 1
fi

(cd "$ROOT_DIR/hub-next" && node scripts/backfill-partner-vcs.mjs)

echo
echo "Done."
