"""Push hub company pages (.md + .docx) to GitHub via the Contents API.

Called after Stage 1 screening when running on Cloud Run (ephemeral filesystem).
Requires GH_TOKEN (a fine-grained PAT with Contents: Read & Write on the repo)
and GH_REPO (e.g. "ocachin/id8-intelligence").

Each file is upserted: if it already exists the current SHA is fetched first so
the PUT doesn't conflict; if it's new it's created. The .docx is base64-encoded
in the PUT body — GitHub accepts binary blobs this way up to ~50 MB.
"""
import base64
import io
import os

import requests

_API = "https://api.github.com"
_BRANCH = os.getenv("GH_BRANCH", "main")


def _headers():
    # .strip(): the secret may carry a trailing newline (echo vs printf), which
    # makes the Authorization header invalid and GitHub rejects every request.
    token = os.getenv("GH_TOKEN", "").strip()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_sha(repo: str, path: str) -> str | None:
    """Return the blob SHA of an existing file, or None if it doesn't exist."""
    r = requests.get(f"{_API}/repos/{repo}/contents/{path}",
                     headers=_headers(), params={"ref": _BRANCH}, timeout=15)
    if r.status_code == 200:
        return r.json().get("sha")
    return None


def _put_file(repo: str, path: str, content_bytes: bytes, message: str, sha: str | None):
    body = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
        "branch": _BRANCH,
    }
    if sha:
        body["sha"] = sha
    r = requests.put(f"{_API}/repos/{repo}/contents/{path}",
                     headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def push_company_screen(slug: str, md_content: str, docx_bytes: bytes,
                        md_path: str, docx_path: str) -> dict:
    """Upsert the markdown page and docx for one company. Returns paths pushed."""
    repo = os.getenv("GH_REPO", "ocachin/id8-intelligence")
    results = {}

    md_sha  = _get_sha(repo, md_path)
    _put_file(repo, md_path, md_content.encode("utf-8"),
              f"deal screen: update {slug} hub page", md_sha)
    results["md"] = md_path

    docx_sha = _get_sha(repo, docx_path)
    _put_file(repo, docx_path, docx_bytes,
              f"deal screen: update {slug}.docx", docx_sha)
    results["docx"] = docx_path

    return results
