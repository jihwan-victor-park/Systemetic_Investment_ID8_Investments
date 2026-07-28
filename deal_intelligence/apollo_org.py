"""Radar's headcount sensor (RADAR_PLAN.md Part III's `headcount` metric,
"Apollo, monthly") -- one bounded organization-enrichment call per Radar
company, feeding capital_clock.py's burn estimate.

Distinct from pipeline/attio_apollo_sync.py, which is a different feature
("Apollo Reach Out" contact sync) using the same API and the same
X-Api-Key header convention, but a different Apollo endpoint (contact
creation, not org enrichment) -- this module doesn't import or reuse that
script, they just happen to share a vendor.

IMPORTANT -- first-implementation-day check: this module was written without
a live Apollo call (no network access in the environment it was authored
in). `estimated_num_employees` is Apollo's documented response field name
for this endpoint as of this writing, but verify it against one real
response before trusting get_org_headcount()'s output in the write path --
see the implementation plan's sequencing step 3.
"""
from datetime import date

from . import config
from .net import session

APOLLO_BASE = "https://api.apollo.io/api/v1"


def _headers():
    return {"X-Api-Key": config.APOLLO_API_KEY, "Content-Type": "application/json", "Cache-Control": "no-cache"}


def get_org_headcount(domain):
    """domain: bare hostname (e.g. "northwindsystems.com"), same normalized
    shape hub-next's `website` field already stores. Returns
    {"headcount": int, "checkedAt": <today's ISO date>} on a match, or None
    on any miss/failure -- NEVER raises, since a headcount lookup is
    enrichment (the capital clock degrades to "no estimate yet" without it,
    see capital_clock.compute()'s missing-headcount branch), not something
    the caller can't function without."""
    if not domain or not config.APOLLO_API_KEY:
        return None
    try:
        r = session.get(
            f"{APOLLO_BASE}/organizations/enrich",
            params={"domain": domain},
            headers=_headers(),
            timeout=15,
        )
        if not r.ok:
            return None
        org = r.json().get("organization") or {}
        headcount = org.get("estimated_num_employees")
        if not isinstance(headcount, int) or headcount <= 0:
            return None
    except Exception:
        # Network/parse failure -- a normal miss for this call, not a hard
        # error. The caller (radar_state.py) treats "no headcount" as an
        # expected, common state, not an exception to handle specially.
        return None
    return {"headcount": headcount, "checkedAt": date.today().isoformat()}
