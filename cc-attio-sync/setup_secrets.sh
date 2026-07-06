#!/usr/bin/env bash
# One-time: create the 4 secrets cc-attio-sync needs, and grant its Cloud Run
# runtime service account access to them. Run this ONCE, before the first
# ./deploy.sh. Safe to re-run later (e.g. to rotate WEBHOOK_SECRET) — it adds a
# new secret version rather than failing if the secret already exists.
#
# Prerequisites:
#   - CC_CLIENT_ID / CC_CLIENT_SECRET from your Constant Contact developer app
#   - CC_REFRESH_TOKEN from `python get_refresh_token.py` (run that first)
#
# Usage:
#   export CC_CLIENT_ID=...
#   export CC_CLIENT_SECRET=...
#   export CC_REFRESH_TOKEN=...
#   export WEBHOOK_SECRET=$(openssl rand -hex 32)   # or set your own
#   ./setup_secrets.sh
set -euo pipefail

PROJECT="${PROJECT:-137750788450}"
RUNTIME_SA="${RUNTIME_SA:-${PROJECT}-compute@developer.gserviceaccount.com}"

for var in CC_CLIENT_ID CC_CLIENT_SECRET CC_REFRESH_TOKEN WEBHOOK_SECRET; do
  : "${!var:?Set $var first (see the comment at the top of this script)}"
done

create_or_add_version() {
  local name="$1" value="$2"
  if gcloud secrets describe "$name" --project="$PROJECT" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- --project="$PROJECT"
  else
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --project="$PROJECT"
  fi
}

for name in CC_CLIENT_ID CC_CLIENT_SECRET CC_REFRESH_TOKEN WEBHOOK_SECRET; do
  create_or_add_version "$name" "${!name}"
done

# CC rotates the refresh token on every use — the running service needs to
# write new versions of just that one secret, on its own, with no human in
# the loop.
gcloud secrets add-iam-policy-binding CC_REFRESH_TOKEN --project="$PROJECT" \
  --member="serviceAccount:${RUNTIME_SA}" --role="roles/secretmanager.secretVersionAdder" >/dev/null

for name in CC_CLIENT_ID CC_CLIENT_SECRET CC_REFRESH_TOKEN WEBHOOK_SECRET; do
  gcloud secrets add-iam-policy-binding "$name" --project="$PROJECT" \
    --member="serviceAccount:${RUNTIME_SA}" --role="roles/secretmanager.secretAccessor" >/dev/null
done

echo "Done. ${RUNTIME_SA} can read all four secrets and rotate CC_REFRESH_TOKEN."
echo "Next: python list_cc_lists.py  ->  paste the mapping into CC_LIST_MAP in deploy.sh  ->  ./deploy.sh"
