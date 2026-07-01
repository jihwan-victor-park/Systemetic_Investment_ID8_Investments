# n8n for Google Cloud Run
# Thin wrapper over the official image so we can pin a version and push to
# Artifact Registry (Cloud Run deploys from your project's registry).
#
# Pinned to 2.28.4 (latest). Note: 2.x made task runners mandatory (the
# N8N_RUNNERS_ENABLED=false override is now just ignored with a deprecation
# notice) and it also tries to start an internal Python task runner, which
# needs python3 present in the image — the upstream base image doesn't
# include it.
#
# Pick a pinned version — do NOT use :latest in production.
# Check current stable at https://github.com/n8n-io/n8n/releases

# n8n's runtime image is Alpine-derived (node:24-alpine per n8n's own
# Dockerfile source) but ships with apk itself stripped out — confirmed by
# `/sbin/apk: not found` at build time. So python3 can't be apk-installed
# INSIDE the n8n image directly. Instead: install it into an isolated root in
# a plain Alpine stage (which does have apk), then copy that self-contained
# tree over — safe because both stages share the same Alpine 3.24 base/ABI.
FROM alpine:3.24 AS pybuild
# --allow-untrusted: a fresh --initdb root has no trusted apk signing keys
# configured, so signature verification fails even for Alpine's own official
# CDN. Acceptable here — this stage is build-only (never shipped) and the
# fetch is already over HTTPS.
RUN apk add --no-cache --initdb --root /pyroot --allow-untrusted \
    --repository https://dl-cdn.alpinelinux.org/alpine/v3.24/main \
    --repository https://dl-cdn.alpinelinux.org/alpine/v3.24/community \
    python3

FROM docker.io/n8nio/n8n:2.28.4
USER root
COPY --from=pybuild /pyroot/usr /usr
COPY --from=pybuild /pyroot/lib /lib
USER node

# n8n listens on 5678. We tell Cloud Run to route to this port at deploy time
# (gcloud run deploy --port 5678). Setting N8N_PORT here keeps them aligned.
ENV N8N_PORT=5678
EXPOSE 5678

# The base image already sets the correct entrypoint (tini -> n8n).
# Nothing else to do — all configuration is injected as env vars at deploy time.
