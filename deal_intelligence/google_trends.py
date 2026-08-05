"""Google Trends sensor for the Heat Score Signal Framework (Oscar's
2026-07-30 xlsx upload) -- feeds radar_market_heat.py's "Industry Growth"
and "Google Trends search interest" rows.

Public data, no login wall, no ToS boundary to cross (unlike Crunchbase's
Growth/Heat/Surge scores -- see radar_market_heat.py's own crunchbase_proxy()
docstring for why those three rows are proxied via Perplexity instead of
scraped). Fetched via `pytrends`, an unofficial wrapper around the same
trends.google.com endpoints the public Trends UI calls.

Known reliability limits, stated plainly rather than papered over:
  - pytrends is unofficial -- Google can start 429-ing or serving CAPTCHAs
    to any IP (cloud IPs, including GCP, are hit more often than
    residential ones) with no advance notice and no SLA.
  - This sandbox's own outbound proxy blocks trends.google.com outright
    (policy denial, confirmed 2026-07-30 and again 2026-08-05) -- this
    module has NOT been live-tested from here. It runs from the user's own
    Cloud Shell / Cloud Run, which has a different egress path; test it
    for real there before trusting its numbers.

Both of these are exactly why every function here returns None (never 0,
never a fabricated number) on any failure -- a rate-limited or blocked
fetch must read as "missing," the same convention capital_clock.py/
radar_timing_signals.py already use for absent data. The caller
(radar_market_heat.py) treats None as "exclude this signal, reweight over
what's left," never as evidence of low interest.
"""
import time

_RETRIES = 2
_RETRY_SLEEP_SECONDS = 3


def _pytrends_client():
    # Imported lazily so a caller that never touches Trends (e.g. every
    # existing test in this repo) doesn't need pytrends importable.
    from pytrends.request import TrendReq
    return TrendReq(hl="en-US", tz=360, timeout=(6, 15))


def _pct_change_vs_prior_period(series):
    """series: a pandas Series of weekly interest values, oldest-first
    (pytrends' own `interest_over_time()` shape). Compares the mean of the
    most recent ~4 weeks (the current month) to the mean of the ~4 weeks
    before that (the preceding month) -- matches the framework's own
    "average percent change in search interest vs. the preceding month"
    wording for Industry Growth, and the equivalent monthly comparison for
    company-name search interest.

    Returns None if there isn't enough history to form both windows, or if
    the prior window averages to 0 (can't compute a percent change off a
    true zero without a divide-by-zero -- reads as "no baseline," not
    "infinite growth")."""
    values = list(series)
    if len(values) < 8:
        return None
    recent = values[-4:]
    prior = values[-8:-4]
    prior_mean = sum(prior) / len(prior)
    if prior_mean <= 0:
        return None
    recent_mean = sum(recent) / len(recent)
    return round((recent_mean - prior_mean) / prior_mean * 100, 1)


def _fetch_pct_change(keyword, client=None, on_error=None):
    """One keyword's pct-change-vs-preceding-month, or None on any failure
    (network, rate limit, no data for the term). Retries a couple of times
    with a short sleep -- pytrends' most common failure is a transient
    429, not a permanent one, so one retry recovers a meaningful fraction
    of calls without turning a batch run into a long wait.

    `on_error(keyword, exception)`: optional callback fired on the FINAL
    failed attempt only (not each retry) -- lets a caller print/log the
    real reason (rate limit vs. no data vs. network) instead of the bare
    None a batch run would otherwise see with no way to tell "Trends is
    being blocked" apart from "this term has no data.\""""
    last_error = None
    for attempt in range(_RETRIES + 1):
        try:
            pt = client or _pytrends_client()
            pt.build_payload([keyword], timeframe="today 3-m")
            df = pt.interest_over_time()
            if df is None or df.empty or keyword not in df.columns:
                # A REAL response, just with nothing in it -- Trends has no
                # search-volume data for this term (common for an obscure
                # private-company name, or a hyper-specific industry tag).
                # This is NOT the same fact as "the call was blocked," and
                # burying both behind an identical silent None makes a
                # working-but-unpopulated Trends call indistinguishable from
                # a rate-limited one -- exactly the ambiguity that made a
                # wall of "MISSING" rows unreadable (Oscar, 2026-07-30).
                if on_error is not None:
                    on_error(keyword, RuntimeError("Trends returned no data for this term (not blocked -- genuinely no search volume)"))
                return None
            result = _pct_change_vs_prior_period(df[keyword])
            if result is None and on_error is not None:
                on_error(keyword, RuntimeError("Trends returned data but not enough weeks of it yet to compare vs. the prior period"))
            return result
        except Exception as e:  # pytrends raises a mix of requests/urllib3
            # errors depending on failure mode -- all of them mean "no
            # reading this call," never "zero interest."
            last_error = e
            if attempt < _RETRIES:
                time.sleep(_RETRY_SLEEP_SECONDS)
    if last_error is not None and on_error is not None:
        on_error(keyword, last_error)
    return None


def industry_growth(industries, client=None, on_error=None):
    """`industries`: the company's tagged sectors (Crunchbase/Apollo
    categories, per the framework's own Source column). Averages each
    industry's own pct-change-vs-preceding-month, skipping any industry
    Trends couldn't resolve -- one obscure category failing to fetch
    shouldn't blank out an otherwise-good read on the rest.

    Returns {"pctChange": float|None, "industriesChecked": [...],
    "industriesFailed": [...]}. pctChange is None (never 0) if every
    industry failed or `industries` was empty -- "no industry tag" and
    "flat search interest" are different facts and must not collapse."""
    industries = [i for i in (industries or []) if i]
    checked, failed, changes = [], [], []
    client = client or None
    for industry in industries:
        pct = _fetch_pct_change(industry, client, on_error=on_error)
        if pct is None:
            failed.append(industry)
        else:
            checked.append(industry)
            changes.append(pct)
    return {
        "pctChange": round(sum(changes) / len(changes), 1) if changes else None,
        "industriesChecked": checked,
        "industriesFailed": failed,
    }


def company_search_interest(name, client=None, on_error=None):
    """Search-interest growth for the company's own name, as a public-
    attention proxy (framework row 11). Returns {"pctChange": float|None}.

    A generic-word company name (e.g. a one-word consumer brand) will
    produce noisy or unrelated Trends data -- a known limitation of using
    the bare name as the query, not fixed here; the framework's own
    "Description" column names this exact tradeoff ("proxy for rising
    public attention", not a precise measurement)."""
    if not name:
        return {"pctChange": None}
    return {"pctChange": _fetch_pct_change(name, client, on_error=on_error)}
