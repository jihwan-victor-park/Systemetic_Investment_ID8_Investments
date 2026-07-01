# n8n for Google Cloud Run
# Thin wrapper over the official image so we can pin a version and push to
# Artifact Registry (Cloud Run deploys from your project's registry).
#
# Pulls from OUR OWN Artifact Registry mirror, not docker.n8n.io directly —
# Cloud Build's shared builder IP pool hits docker.n8n.io's anonymous-pull rate
# limit constantly. Mirror a new version once (see MIGRATION_PLAN.md / repo
# history) with:
#   docker pull docker.n8n.io/n8nio/n8n:<version>
#   gcloud auth configure-docker us-east4-docker.pkg.dev --quiet
#   docker tag docker.n8n.io/n8nio/n8n:<version> \
#     us-east4-docker.pkg.dev/molten-crowbar-498920-q8/n8n/n8n-upstream:<version>
#   docker push us-east4-docker.pkg.dev/molten-crowbar-498920-q8/n8n/n8n-upstream:<version>
# then update the tag below to match.
#
# Check current stable at https://github.com/n8n-io/n8n/releases
FROM us-east4-docker.pkg.dev/molten-crowbar-498920-q8/n8n/n8n-upstream:1.123.62

# n8n listens on 5678. We tell Cloud Run to route to this port at deploy time
# (gcloud run deploy --port 5678). Setting N8N_PORT here keeps them aligned.
ENV N8N_PORT=5678
EXPOSE 5678

# The base image already sets USER node and the correct entrypoint (tini -> n8n).
# Nothing else to do — all configuration is injected as env vars at deploy time.
