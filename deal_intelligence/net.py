"""Shared HTTP session for every external call in this package (Perplexity,
Anthropic, Attio, GitHub). A bare requests.post(...).raise_for_status() has no
resilience to a dropped connection, a request timeout, or a provider's 429/5xx
-- one blip fails the whole deal's scoring (or write-back) outright. Route all
calls through `session` instead of the requests module directly.

Retries happen at the transport layer (urllib3), so call sites are unchanged:
still call session.post/get/patch/put(...) and still call .raise_for_status()
-- that still fires normally once retries are exhausted.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_RETRY = Retry(
    total=4,                  # up to 4 retries (5 attempts total)
    backoff_factor=1.5,       # ~0s, 1.5s, 3s, 6s, 12s between attempts
    backoff_jitter=0.5,
    status_forcelist=(429, 500, 502, 503, 504),  # not plain 4xx -- retrying a bad request won't fix it
    allowed_methods=("GET", "POST", "PUT", "PATCH", "DELETE"),
    raise_on_status=False,    # let the caller's raise_for_status() handle the final failure
    respect_retry_after_header=True,
)

session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=_RETRY))
session.mount("http://", HTTPAdapter(max_retries=_RETRY))
