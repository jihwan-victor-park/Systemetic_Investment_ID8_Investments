"""Radar's per-sensor time series storage (RADAR_SIGNAL_ENGINE.md §5 "time
series, not lookups" -- a single scrape is nearly worthless; the derivative
across samples is the signal). RADAR_PLAN.md Part VIII's shape:
companies/{slug}/signalSeries/{sensor}, ONE doc per sensor holding a capped
array of {date, value} samples -- not one Firestore doc per sample -- so
reading a company's full sensor history stays a single read, matching the
hub's own "denormalize for one read" performance lesson.

Same "thin I/O wrapper, pure math split out" shape as apollo_org.py/
radar_jobs.py: append_sample/read_series touch Firestore, growth_rate is a
pure function, unit-testable with a fabricated list.
"""
from datetime import date, timedelta

DEFAULT_CAP = 24


def _series_ref(db, slug, sensor):
    return db.collection("companies").document(slug).collection("signalSeries").document(sensor)


def append_sample(db, slug, sensor, sample_date, value, cap=DEFAULT_CAP):
    """Appends {date, value} to the sensor's capped array, oldest-first,
    trimmed to the most recent `cap` entries. Reads the existing doc first
    -- there's no atomic "push and cap" Firestore primitive -- fine at
    Radar's per-scan-per-sensor call volume, same read-then-write shape
    recompute_and_write already uses for the company doc itself.

    Replaces a same-day sample rather than duplicating it, so a company
    recomputed twice in one day (a scan immediately followed by an Attio
    import touching the same company) doesn't double-count a day in
    growth_rate's window."""
    date_str = sample_date.isoformat() if isinstance(sample_date, date) else str(sample_date)[:10]
    ref = _series_ref(db, slug, sensor)
    existing = ref.get().to_dict() or {}
    samples = [s for s in existing.get("samples", []) if s.get("date") != date_str]
    samples.append({"date": date_str, "value": value})
    samples.sort(key=lambda s: s["date"])
    samples = samples[-cap:]
    ref.set({"samples": samples, "updatedAt": date_str}, merge=True)
    return samples


def read_series(db, slug, sensor):
    """Returns the sensor's [{date, value}, ...] samples, oldest-first, or
    [] if none exist yet (a company on its first scan, or a sensor that
    hasn't run for it)."""
    doc = _series_ref(db, slug, sensor).get()
    if not doc.exists:
        return []
    return (doc.to_dict() or {}).get("samples", [])


def growth_rate(series, window_days=90):
    """Annualized % change over the most recent `window_days` of a
    [{date, value}, ...] series (oldest-first) -- the input
    SIGNAL_KERNELS["headcount_growth_40"]/["headcount_decline_10"]
    (radar_hazard.py) need. Compares the latest sample to the oldest
    sample still inside the window -- not a linear regression; two points
    is enough signal at Radar's monthly sample cadence, and matches
    RADAR_SIGNAL_ENGINE.md §3's own worked example (a 40→94 heads over 7
    months two-point comparison).

    Returns None with fewer than 2 samples total -- can't compute a rate
    from one point -- caller treats None as "no growth signal yet," same
    as capital_clock's own missing-data convention."""
    if len(series) < 2:
        return None
    latest = series[-1]
    latest_date = date.fromisoformat(latest["date"])
    cutoff = latest_date - timedelta(days=window_days)
    window = [s for s in series if date.fromisoformat(s["date"]) >= cutoff]
    if len(window) < 2:
        # Whole series is younger than the window -- still directionally
        # useful early on, rather than refusing to compute anything until
        # `window_days` of history has accumulated.
        window = series
    oldest = window[0]
    oldest_date = date.fromisoformat(oldest["date"])
    days_elapsed = (latest_date - oldest_date).days
    if days_elapsed <= 0 or not oldest.get("value"):
        return None
    total_change = (latest["value"] - oldest["value"]) / oldest["value"]
    annualized = total_change * (365.0 / days_elapsed)
    return round(annualized, 4)


def mom_growth_rate(series, min_gap_days=21):
    """Literal month-over-month % change -- latest sample vs. the most
    recent PRIOR sample at least `min_gap_days` older (a real prior
    reading, not a same-week duplicate at Radar's monthly Apollo/weekly
    job-board cadence). Distinct from growth_rate() above, which is
    annualized over a 90-day window for radar_hazard.py's kernels -- this
    is the literal MoM rate the Heat Score Signal Framework's rubric asks
    for directly (see radar_market_heat.py).

    Returns None with fewer than 2 samples, or if no sample in the series
    is old enough to count as "last month" yet (e.g. a company's first two
    reads landed a week apart)."""
    if len(series) < 2:
        return None
    latest = series[-1]
    latest_date = date.fromisoformat(latest["date"])
    candidates = [s for s in series[:-1] if (latest_date - date.fromisoformat(s["date"])).days >= min_gap_days]
    if not candidates:
        return None
    prior = candidates[-1]  # closest-to-a-month-ago prior sample
    if not prior.get("value"):
        return None
    return round((latest["value"] - prior["value"]) / prior["value"], 4)
