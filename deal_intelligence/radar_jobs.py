"""Radar's job-board sensor (RADAR_SIGNAL_ENGINE.md §5.1 "job postings" --
F2, the highest-value signal family: hiring COMPOSITION, not volume, is
what discriminates "preparing to raise" from "just closed"). Free, public
ATS APIs -- no vendor key, no LLM.

Two-step shape: detect_ats() finds which ATS a company uses (once, cached
by the caller on company.radar.ats), fetch_postings() pulls its current
open roles from that ATS's public JSON API, classify_postings() buckets
them by seniority/function with a plain keyword match -- same "high
recall, deterministic" convention this codebase uses elsewhere for
classification, no LLM call.

Apollo's own job-postings surface is NOT used here -- RADAR_PLAN.md flags
it as unverified against a live response, whereas Greenhouse/Lever/Ashby
are free, public, and need no license check at all. Apollo headcount
(apollo_org.py) is unrelated and unaffected -- this module doesn't import
or reuse it.
"""
import re
from datetime import datetime, timezone

from .net import session

_ATS_PATTERNS = (
    ("greenhouse", re.compile(r"boards\.greenhouse\.io/([a-zA-Z0-9_-]+)")),
    ("lever", re.compile(r"jobs\.lever\.co/([a-zA-Z0-9_-]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)")),
)

_FEED_URL = {
    "greenhouse": lambda token: f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
    "lever": lambda token: f"https://api.lever.co/v0/postings/{token}?mode=json",
    "ashby": lambda token: f"https://api.ashbyhq.com/posting-api/job-board/{token}",
}

# Maps 1:1 onto radar_hazard.SIGNAL_KERNELS' four hiring-composition rows
# (senior_finance_role/corp_dev_role/senior_gtm_burst/recruiter_hiring) --
# keys here ARE the bucket names radar_state.py reads to decide which
# kernel fires.
_TITLE_KEYWORDS = {
    "rolesSeniorFinance": (
        "cfo", "chief financial officer", "vp finance", "vp, finance",
        "vice president finance", "vice president, finance",
        "head of finance", "controller", "vp fp&a", "head of fp&a",
    ),
    "rolesCorpDev": (
        "corp dev", "corporate development", "head of corp dev",
        "vp corporate development", "m&a",
    ),
    "rolesExecGTM": (
        "chief revenue officer", "cro", "vp sales", "vp, sales",
        "vice president sales", "vice president, sales", "head of sales",
        "vp revenue", "head of revenue",
    ),
    "rolesRecruiting": (
        "recruiter", "talent acquisition", "recruiting", "sourcer",
        "head of talent", "vp talent",
    ),
}


def detect_ats(website):
    """Fetches the company's site (bare GET via the shared retry session
    apollo_org.py also uses) and regex-matches known ATS embed URLs.
    Returns {"provider": ..., "token": ...} on a match, or None. Caller
    (radar_state.py) stores the result on company.radar.ats and never calls
    this again once set (RADAR_PLAN.md §2.2's "one-time setup per
    company"). NEVER raises -- a detection miss is a normal, common state,
    same convention as apollo_org.get_org_headcount()."""
    if not website:
        return None
    url = website if website.startswith("http") else f"https://{website}"
    try:
        r = session.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if not r.ok:
            return None
        html = r.text
    except Exception:
        return None
    for provider, pattern in _ATS_PATTERNS:
        match = pattern.search(html)
        if match:
            return {"provider": provider, "token": match.group(1)}
    return None


def _epoch_ms_to_iso(ms):
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def fetch_postings(provider, token):
    """One free GET against the detected ATS's public postings API. Returns
    [{"title": ..., "department": ..., "firstSeen": <ISO date or None>}].
    `firstSeen` comes straight from the ATS when it exposes a creation date
    (Lever/Ashby do; Greenhouse's board API doesn't, so it's None there --
    classify_postings' own diff against the stored title series is what
    establishes "first seen BY US" for a Greenhouse company). Returns []
    on any failure -- never raises, matches detect_ats/apollo_org's
    convention."""
    build_url = _FEED_URL.get(provider)
    if not build_url or not token:
        return []
    try:
        r = session.get(build_url(token), timeout=15)
        if not r.ok:
            return []
        data = r.json()
    except Exception:
        return []

    if provider == "greenhouse":
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        return [
            {"title": j.get("title", ""), "department": (j.get("departments") or [{}])[0].get("name", ""), "firstSeen": None}
            for j in jobs
        ]
    if provider == "lever":
        jobs = data if isinstance(data, list) else []
        return [
            {"title": j.get("text", ""), "department": (j.get("categories") or {}).get("team", ""), "firstSeen": _epoch_ms_to_iso(j.get("createdAt"))}
            for j in jobs
        ]
    if provider == "ashby":
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        return [
            {"title": j.get("title", ""), "department": j.get("department", ""), "firstSeen": (j.get("publishedAt") or "")[:10] or None}
            for j in jobs
        ]
    return []


def _match_bucket(title):
    t = (title or "").lower()
    for bucket, keywords in _TITLE_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return bucket
    return None


def classify_postings(postings, previously_seen_titles=()):
    """Pure classifier -- no LLM, no I/O. Buckets postings by a plain title
    keyword match, and separately reports which of THIS scan's matched
    titles are new since `previously_seen_titles` (the prior scan's title
    list, read by the caller from radar_signal_series's "jobs" sensor
    series) -- that "new since last scan" set is what gives
    radar_hazard.py's senior_finance_role/corp_dev_role/senior_gtm_burst/
    recruiter_hiring signals a real first-seen date (today, since that's
    when WE first observed it), not just a point-in-time count.

    Returns {"counts": {bucket: n}, "newTitles": {bucket: [title, ...]},
    "allTitlesSeen": [title, ...]} -- `allTitlesSeen` is what the caller
    persists as this scan's series sample for next time's diff."""
    counts = {bucket: 0 for bucket in _TITLE_KEYWORDS}
    new_titles = {bucket: [] for bucket in _TITLE_KEYWORDS}
    all_titles = []
    seen = set(previously_seen_titles)
    for posting in postings:
        title = posting.get("title", "")
        bucket = _match_bucket(title)
        if not bucket:
            continue
        counts[bucket] += 1
        all_titles.append(title)
        if title not in seen:
            new_titles[bucket].append(title)
    return {"counts": counts, "newTitles": new_titles, "allTitlesSeen": all_titles}
