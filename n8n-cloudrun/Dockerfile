# n8n for Google Cloud Run
# Thin wrapper over the official image so we can pin a version and push to
# Artifact Registry (Cloud Run deploys from your project's registry).
#
# Pinned to 2.28.4 (latest). Note: 2.x made task runners mandatory (the
# N8N_RUNNERS_ENABLED=false override is now just ignored with a deprecation
# notice) and it also tries to start an internal Python task runner, which
# needs python3 present in the image — the upstream base image doesn't
# include it, hence installing it below.
#
# Pick a pinned version — do NOT use :latest in production.
# Check current stable at https://github.com/n8n-io/n8n/releases
FROM docker.io/n8nio/n8n:2.28.4

# Install python3 for n8n's internal Python task runner. Switch to root only
# for the install (matching the base image's non-root runtime posture
# otherwise); detect apk vs apt-get since the base OS isn't guaranteed.
USER root
RUN (command -v apk >/dev/null 2>&1 && apk add --no-cache python3) || \
    (apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*)
USER node

# n8n listens on 5678. We tell Cloud Run to route to this port at deploy time
# (gcloud run deploy --port 5678). Setting N8N_PORT here keeps them aligned.
ENV N8N_PORT=5678
EXPOSE 5678

# The base image already sets the correct entrypoint (tini -> n8n).
# Nothing else to do — all configuration is injected as env vars at deploy time.
