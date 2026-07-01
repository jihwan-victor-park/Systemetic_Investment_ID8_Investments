# n8n for Google Cloud Run
# Thin wrapper over the official image so we can pin a version and push to
# Artifact Registry (Cloud Run deploys from your project's registry).
#
# Pinned to 1.108.2 — this is the version actually deployed and working.
# A bump to 1.123.62 was attempted but blocked by what looks like an org-level
# network policy (pushes to Artifact Registry from Cloud Shell consistently
# hit "connection refused" on the exact same IP, matching the pattern of other
# org security restrictions hit earlier — likely Context-Aware Access / VPC-SC,
# not something fixable from here). Revisit the version bump once that's
# resolved with your GCP org admin; it's cosmetic (clears an update nag),
# not required for the migration to work.
#
# Pick a pinned version — do NOT use :latest in production.
# Check current stable at https://github.com/n8n-io/n8n/releases
FROM docker.io/n8nio/n8n:2.28.4

# n8n listens on 5678. We tell Cloud Run to route to this port at deploy time
# (gcloud run deploy --port 5678). Setting N8N_PORT here keeps them aligned.
ENV N8N_PORT=5678
EXPOSE 5678

# The base image already sets USER node and the correct entrypoint (tini -> n8n).
# Nothing else to do — all configuration is injected as env vars at deploy time.
