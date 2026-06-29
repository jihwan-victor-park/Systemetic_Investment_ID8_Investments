"""
Load secrets into os.environ from Google Cloud Secret Manager.

Runs once at import time. On Cloud Run the service account has secretAccessor
on the project, so no extra auth is needed. Locally, falls back to whatever is
already in the environment (populated by python-dotenv in config.py).

Secret resource names follow the pattern:
  projects/137750788450/secrets/<NAME>/versions/latest
"""
import os

_GCP_PROJECT = "projects/137750788450"

_SECRETS = {
    "ATTIO_API_KEY":       f"{_GCP_PROJECT}/secrets/ATTIO_API_KEY",
    "PERPLEXITY_API_KEY":  f"{_GCP_PROJECT}/secrets/PERPLEXITY_API_KEY",
    "APOLLO_API_KEY":      f"{_GCP_PROJECT}/secrets/APOLLO_API_KEY",
}


def _load():
    try:
        from google.cloud import secretmanager  # type: ignore
    except ImportError:
        # Library not installed — local dev without the GCP SDK, rely on .env
        return

    client = secretmanager.SecretManagerServiceClient()
    for env_var, resource in _SECRETS.items():
        if os.environ.get(env_var):
            # Already set (e.g. injected by Cloud Run secret env-var binding or .env)
            continue
        try:
            response = client.access_secret_version(name=f"{resource}/versions/latest")
            os.environ[env_var] = response.payload.data.decode("utf-8").strip()
        except Exception as exc:  # noqa: BLE001
            # Non-fatal: missing secret just means the key stays unset and the
            # relevant endpoint will return a 400 as it does today.
            print(f"[secrets] could not load {env_var}: {exc}")


_load()
