"""Radar's orchestrator (RADAR_PLAN.md Parts I/III/IV/VI/VIII) -- the sole
writer of `companies/{slug}.radar`. Ties radar_mandate.screen() +
capital_clock.compute() + radar_schedule.next_scan_at() +
radar_hazard.compute() together.

Seasonality shifting of the clock's raw dates happens HERE, not inside
capital_clock.compute() -- see that module's own docstring for why.
predictedWindowOpen shifts LATER (never predicts a launch into a dead
zone); contactByDate shifts EARLIER (never lets our own deadline chase a
dead zone); alertAtDate is re-derived from the SHIFTED contactByDate, not
capital_clock's raw one.

Auto-drop-from-view (RADAR_SIGNAL_ENGINE.md's own "nothing is ever
deleted" principle, Oscar 2026-07-29 "auto-remove from Radar view, not
auto-delete the record"): a company whose heatPoints sits below the
hub-editable watch floor for DROP_STREAK_THRESHOLD consecutive scans gets
`radar.droppedAt` stamped, ONCE, and never touched again by this module --
a human restores it by hand. hub-next's radar/page.jsx filter is what
actually hides a dropped company; a company whose real `stage` is literally
'radar' can't have that stage removed by a tag operation, so droppedAt is
the only signal that matters there too.
"""
from datetime import date, timedelta

from google.cloud import firestore

from . import (apollo_org, capital_clock, config, radar_access, radar_calibration, radar_hazard,
               radar_jobs, radar_mandate, radar_schedule, radar_signal_series, radar_timing_signals)

_db = None
SCHEMA_VERSION = 1
APOLLO_STALENESS_DAYS = 30
CRITICAL_ZONE_MONTHS = 5  # matches radar_schedule.base_interval_weeks' own 3-5mo critical-zone band

DEFAULT_WATCH_FLOOR = 5  # 0-100 scale (Oscar, 2026-07-29, corrected same day -- 25 was above what ANY
# company can reach with zero active signals ever fired: baseline_hazard's own lowest bucket (no
# clock data, or window >12mo out) with no active signal produces heatPoints ~7-9.5, so a floor of
# 25 auto-dropped every single passing company within DROP_STREAK_THRESHOLD scans regardless of
# whether anything was actually wrong -- happened in production the same day this was built. 5 sits
# BELOW that "no signal yet" floor (~7.2 minimum) and ABOVE what a genuine negative signal (headcount
# decline/layoffs, composite multiplier <1) pulls a company down to (~2-4.5) -- see radar_hazard.py's
# SIGNAL_KERNELS negative-family rows. Auto-drop should only fire on real quiet/declining evidence,
# never on "hasn't been scanned yet." Hub-editable via radarConfig/current, same doc
# RadarHeatSettings.jsx writes hotThreshold to.
DROP_STREAK_THRESHOLD = 3  # consecutive below-floor scans before auto-drop -- matches radar_schedule's own dwell-time spirit (don't flicker on one bad week)

# Maps radar_jobs.classify_postings' bucket names onto radar_hazard.
# SIGNAL_KERNELS' hiring-composition rows -- 1:1, this IS the wiring
# between "what the job-board sensor found" and "which kernel fires."
_BUCKET_TO_KERNEL = {
    "rolesSeniorFinance": "senior_finance_role",
    "rolesCorpDev": "corp_dev_role",
    "rolesExecGTM": "senior_gtm_burst",
    "rolesRecruiting": "recruiter_hiring",
}


def _firestore():
    global _db
    if _db is None:
        _db = firestore.Client(project=config.GCP_PROJECT_ID)
    return _db


def fields_from_company_doc(data):
    """Builds the `fields` dict compute_radar_state/recompute_and_write
    expect, from an already-fetched company document's data -- shared by
    radar_backfill.py and radar_scan_runner.py so the two don't drift on
    which denormalized fields to read. `hq` falls back to origin.hq for a
    company whose top-level hq was never separately set (there's no
    hub-editable top-level `hq` field the way round/roundDate/roundSize
    have -- origin.hq is the only copy that exists)."""
    return {
        "name": data.get("name"),
        "hq": data.get("hq") or (data.get("origin") or {}).get("hq"),
        "series": data.get("round"),
        "top10VC": data.get("top10VC", False),
        "roundSize": data.get("roundSize"),
        "roundDate": data.get("roundDate"),
        "radarCategory": data.get("radarCategory"),
        "description": data.get("description"),
        "website": data.get("website"),
    }


def list_top_vcs(db=None):
    """Reads the same `topVCs` Firestore collection hub-next's
    listTopVCs() reads -- {name, deals: [{company, ...}], ...} per doc.
    Feeds radar_mandate.build_tier1_index() for S3. Not cached here (unlike
    hub-next's unstable_cache wrapper) -- a caller building a tier1_index
    for a bulk operation (backfill, scan runner, an Attio-import loop)
    should call this ONCE and reuse the result, never per company."""
    db = db or _firestore()
    return [doc.to_dict() for doc in db.collection("topVCs").stream()]


def list_partner_vcs(db=None):
    """Reads the same `partnerVCs` Firestore collection hub-next's
    listPartnerVCs() reads -- {name, portfolio: [{company, ...}], ...} per
    doc. Feeds radar_access.build_partner_index() the same way
    list_top_vcs() feeds radar_mandate.build_tier1_index() -- call ONCE per
    bulk operation, reuse the result."""
    db = db or _firestore()
    return [doc.to_dict() for doc in db.collection("partnerVCs").stream()]


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _hotness(months_until_window):
    """'hot' inside the critical zone (<=5 months until predictedWindowOpen)
    or already past the window (months_until_window < 0); 'cold' otherwise.
    None when there's no window estimate at all yet (no headcount, so
    capital_clock couldn't compute one) -- distinct from "far out and
    quiet", which is a real 'cold', not an unknown."""
    if months_until_window is None:
        return None
    return "hot" if months_until_window <= CRITICAL_ZONE_MONTHS else "cold"


def _active_signals(headcount_growth, job_signals, today):
    """Turns this scan's raw sensor reads into radar_hazard.compute()'s
    `active_signals` list.

    `job_signals`: {bucket: {"firstSeenDate": iso}} for buckets currently
    holding at least one open posting -- recompute_and_write's I/O layer
    tracks firstSeenDate across scans (a kernel's age is "months since
    first seen," not "is it new this exact scan"), so this stays pure: it
    only converts an already-resolved date into an age.

    `headcount_growth`: annualized rate from radar_signal_series.
    growth_rate(), or None with too little history. Concurrent signals
    (headcount growth/decline) are always passed monthsSinceEvent=0 --
    they're re-evaluated fresh every scan rather than aged from an event
    date, see radar_hazard.py's own docstring.

    'layoffs' has a defined kernel in radar_hazard.SIGNAL_KERNELS but no
    sensor this pass (needs a news/press feed) -- it never appears here,
    same as the doc's other not-yet-built rows (press rumor, board member
    added, founder cadence, ...)."""
    signals = []
    for bucket, kernel_key in _BUCKET_TO_KERNEL.items():
        info = (job_signals or {}).get(bucket)
        if not info or not info.get("firstSeenDate"):
            continue
        first_seen = _parse_date(info["firstSeenDate"])
        months_since = round((today - first_seen).days / 30.44, 1) if first_seen else None
        signals.append({"key": kernel_key, "monthsSinceEvent": months_since})
    if headcount_growth is not None:
        if headcount_growth >= 0.40:
            signals.append({"key": "headcount_growth_40", "monthsSinceEvent": 0})
        elif headcount_growth <= -0.10:
            signals.append({"key": "headcount_decline_10", "monthsSinceEvent": 0})
    return signals


def compute_radar_state(fields, tier1_index, headcount, headcount_checked_at,
                         last_scan_at, scan_count, today=None, advance_scan=True,
                         headcount_growth=None, job_signals=None,
                         low_score_streak=0, watch_floor=DEFAULT_WATCH_FLOOR,
                         partner_index=None, latest_screen=None, cost_per_head_overrides=None):
    """Pure orchestration -- no I/O, unit-testable with fabricated inputs.

    fields: {name, hq, series, top10VC, roundSize, roundDate, radarCategory,
    description}. Short-circuits on mandate failure: no clock/schedule/
    hazard/access computed at all, matching Part IV guardrail #1
    ("mandatePass = false -> no sensing, no escalation, ever").

    `headcount_growth`/`job_signals`: this scan's sensor reads, already
    fetched by the caller (recompute_and_write) -- see _active_signals()
    for their shape. `low_score_streak`/`watch_floor` drive auto-drop
    tracking (RADAR_SIGNAL_ENGINE.md's own "nothing is ever deleted"
    principle) -- this function only computes the NEW streak value; the
    caller decides whether crossing DROP_STREAK_THRESHOLD actually stamps
    `droppedAt`, since that's a once-only, never-reset write this function
    (stateless, called fresh every time) has no business owning.

    `partner_index`: radar_access.build_partner_index()'s output (or None,
    treated as empty -- no co-invest match, degrades to institutional/none
    only). A SEPARATE gate from `hazard`, deliberately -- see
    radar_access.py's own module docstring for why timing and access don't
    get blended into one number.

    `advance_scan`: True when this call represents an actual scan happening
    now (the daily scan runner, or the initial backfill) -- scanCount
    increments and lastScanAt stamps today. False when it's an opportunistic
    recompute triggered by an unrelated Attio import (mandate/clock/
    nextScanAt still refresh with the latest data, but scanCount/lastScanAt
    are left exactly as they were, so an import doesn't masquerade as a scan
    that didn't actually happen)."""
    today = today or date.today()
    mandate = radar_mandate.screen(
        {"name": fields.get("name"), "hq": fields.get("hq"), "series": fields.get("series"),
         "deal_size": fields.get("roundSize"), "top10VC": fields.get("top10VC")},
        tier1_index,
    )
    if not mandate["pass"]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "computedAt": today.isoformat(),
            "mandate": mandate,
            "clock": None,
            "schedule": None,
            "hotness": None,
            "hazard": None,
            "access": None,
            "lowScoreStreak": 0,
        }

    region = radar_mandate.classify_region(fields.get("hq"))

    # Timing signals extracted from the company's own Stage 1 screen
    # (radar_timing_signals.py) -- BEFORE the clock, because the growth tier
    # it produces is a clock input (it drives the cadence model, see
    # capital_clock.CADENCE_MONTHS_BY_GROWTH). Kernel ages are measured from
    # the screen's date: a "process is visible" read off a six-month-old
    # screen genuinely is staler than one from today, and the kernels
    # already know how to decay that.
    screen_date = _parse_date((latest_screen or {}).get("date"))
    months_since_screen = round((today - screen_date).days / 30.44, 1) if screen_date else 0
    timing = radar_timing_signals.extract(latest_screen, months_since_screen)

    clock = capital_clock.compute(
        {"roundSize": fields.get("roundSize"), "roundDate": fields.get("roundDate"), "region": region,
         "radarCategory": fields.get("radarCategory"), "description": fields.get("description"),
         "headcountCheckedAt": headcount_checked_at},
        headcount, today, growth_tier=timing["growthTier"],
        cost_per_head_overrides=cost_per_head_overrides,
    )

    predicted_window_open = clock["predictedWindowOpen"]
    contact_by_date = clock["contactByDate"]
    if predicted_window_open:
        shifted_open = radar_schedule.shift_out_of_dead_zone(date.fromisoformat(predicted_window_open), "later")
        clock["predictedWindowOpen"] = shifted_open.isoformat()
    if contact_by_date:
        shifted_contact = radar_schedule.shift_out_of_dead_zone(date.fromisoformat(contact_by_date), "earlier")
        clock["contactByDate"] = shifted_contact.isoformat()
        clock["alertAtDate"] = (shifted_contact - timedelta(weeks=6)).isoformat()

    months_until_window = None
    if clock["predictedWindowOpen"]:
        window_date = date.fromisoformat(clock["predictedWindowOpen"])
        months_until_window = round((window_date - today).days / 30.44, 1)

    # F2 (hiring/headcount, sensed here) + F1/F3/F4 (extracted from the
    # Stage 1 screen above). Combining them is what finally makes
    # radar_hazard's two-family guardrail reachable -- until this pass every
    # available signal was F2, so `twoFamilyPass` could never be True and
    # §4.2's main defense against a single noisy sensor manufacturing
    # conviction was inert.
    active_signals = _active_signals(headcount_growth, job_signals, today) + timing["signals"]
    h0 = radar_hazard.baseline_hazard(months_until_window)
    hazard = radar_hazard.compute(h0, active_signals)
    hazard["computedAt"] = today.isoformat()
    hazard["growthTier"] = timing["growthTier"]
    hazard["growthVerified"] = timing["growthVerified"]
    hazard["growthEvidence"] = timing["growthEvidence"]
    hazard["sourceScreenDate"] = timing["sourceScreenDate"]

    access = radar_access.resolve_access(
        fields.get("name"), mandate.get("tier1Firms"), mandate.get("top10VCFlag"), partner_index or {}
    )

    heat_points = hazard["heatPoints"]
    low_score_streak_out = 0 if heat_points >= watch_floor else low_score_streak + 1

    # Any active F2 signal -> radar_schedule's own "preparation signal
    # active" 6-week floor, finally wired now that a sensor exists to set
    # it True (previously every caller passed False -- see that module's
    # docstring).
    preparation_signal_active = bool(active_signals)
    next_scan_date, next_scan_reason = radar_schedule.next_scan_at(
        last_scan_at, _parse_date(fields.get("roundDate")), scan_count,
        months_until_window, clock["capitalIntensity"], today,
        preparation_signal_active=preparation_signal_active,
    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "computedAt": today.isoformat(),
        "mandate": mandate,
        "clock": clock,
        "schedule": {
            "nextScanAt": next_scan_date.isoformat(),
            "nextScanReason": next_scan_reason,
            "scanCount": scan_count + 1 if advance_scan else scan_count,
            "lastScanAt": today.isoformat() if advance_scan else (last_scan_at.isoformat() if last_scan_at else None),
        },
        "hotness": _hotness(months_until_window),
        "hazard": hazard,
        "access": access,
        "lowScoreStreak": low_score_streak_out,
    }


def _is_stale(checked_at, today):
    parsed = _parse_date(checked_at)
    if not parsed:
        return True
    return (today - parsed).days > APOLLO_STALENESS_DAYS


def _get_watch_floor(db):
    """Reads the same radarConfig/current doc RadarHeatSettings.jsx (hub-
    next) writes `watchFloor` to -- one hub-editable knob shared by both
    languages, same doc lib/radarConfig.js already reads hotThreshold/
    hotWindowMonths from. Missing doc/field falls back to
    DEFAULT_WATCH_FLOOR, mirroring lib/radarConfig.js's own DEFAULTS
    convention."""
    doc = db.collection("radarConfig").document("current").get()
    data = doc.to_dict() or {}
    try:
        return float(data.get("watchFloor", DEFAULT_WATCH_FLOOR))
    except (TypeError, ValueError):
        return DEFAULT_WATCH_FLOOR


def _get_cost_per_head_overrides(db):
    """Reads radarConfig/current.costPerHeadOverrides -- see capital_clock.
    cost_per_head()'s own docstring. Missing doc/field returns {} (no
    overrides, hardcoded COST_PER_HEAD stays authoritative), same graceful-
    default convention as _get_watch_floor."""
    doc = db.collection("radarConfig").document("current").get()
    data = doc.to_dict() or {}
    overrides = data.get("costPerHeadOverrides")
    return overrides if isinstance(overrides, dict) else {}


def recompute_and_write(slug, fields, tier1_index, entry_source, db=None, apollo_lookup=None, today=None, watch_floor=None, partner_index=None, cost_per_head_overrides=None):
    """The one function both the Attio-import hook and the scan runner call.
    Reads the company's existing radar.clock.headcountCheckedAt off
    Firestore first; only calls Apollo if missing or >30 days stale -- keeps
    the Attio-import hook cheap even on a bulk import, and it's the SAME
    staleness rule the scan runner uses, so the two paths never disagree
    about when a fresh Apollo call is warranted.

    entry_source: 'attio-import' | 'backfill' | 'scan-runner' -- stamped for
    audit, and also decides `advance_scan` (see compute_radar_state):
    'backfill'/'scan-runner' count as a real scan, 'attio-import' does not.

    `watch_floor`: pass explicitly (radar_backfill.py does, once, the same
    way it already reuses one tier1_index across a whole run) to avoid a
    radarConfig read per company; None reads it here.

    `partner_index`: radar_access.build_partner_index()'s output -- pass
    explicitly (same reuse-across-a-run convention as tier1_index) or leave
    None to degrade gracefully (access resolves to institutional/none only,
    never co-invest) rather than reading partnerVCs per company.

    Writes via `company_ref.set({'radar': {...}}, merge=True)` -- same
    convention as the rest of firestore_push.py."""
    db = db or _firestore()
    apollo_lookup = apollo_lookup or apollo_org.get_org_headcount
    today = today or date.today()
    if watch_floor is None:
        watch_floor = _get_watch_floor(db)
    if cost_per_head_overrides is None:
        cost_per_head_overrides = _get_cost_per_head_overrides(db)

    company_ref = db.collection("companies").document(slug)
    existing = company_ref.get().to_dict() or {}
    existing_radar = existing.get("radar") or {}
    existing_clock = existing_radar.get("clock") or {}
    existing_schedule = existing_radar.get("schedule") or {}
    existing_hazard = existing_radar.get("hazard") or {}
    existing_job_signals = existing_radar.get("jobSignals") or {}
    already_dropped = existing_radar.get("droppedAt")

    headcount = existing_clock.get("headcount")
    headcount_checked_at = existing_clock.get("headcountCheckedAt")
    if _is_stale(headcount_checked_at, today):
        domain = fields.get("website") or fields.get("domain")
        result = apollo_lookup(domain) if domain else None
        if result:
            headcount = result["headcount"]
            headcount_checked_at = result["checkedAt"]

    # Time-series storage (RADAR_SIGNAL_ENGINE.md §5: "every sensor stores a
    # time series, the prediction reads derivatives"). Appended every call,
    # not just on a fresh Apollo hit -- a repeated cached reading between
    # refreshes is itself informative (flat headcount = a real, honest
    # zero-growth read, not a gap), and append_sample already dedupes
    # same-day entries so a bulk Attio-import burst doesn't spam the series.
    headcount_series = []
    if headcount is not None:
        headcount_series = radar_signal_series.append_sample(db, slug, "headcount", today, headcount)
    headcount_growth = radar_signal_series.growth_rate(headcount_series) if headcount_series else None

    # Job-board sensor (F2) -- gated on the watch floor
    # (RADAR_SIGNAL_ENGINE.md §6 Clock 2's attention-tier idea, simplified
    # to one on/off gate rather than a full tier suite): a company whose
    # last computed heat never cleared watchFloor isn't worth the extra
    # HTTP round-trips. A company with no hazard reading yet (its very
    # first scan) still gets one look, to seed the series.
    prior_heat = existing_hazard.get("heatPoints")
    run_jobs_sensor = prior_heat is None or prior_heat >= watch_floor
    ats = existing_radar.get("ats")
    job_signals = dict(existing_job_signals)
    if run_jobs_sensor:
        if not ats:
            website = fields.get("website")
            ats = radar_jobs.detect_ats(website) if website else None
        if ats:
            postings = radar_jobs.fetch_postings(ats["provider"], ats["token"])
            classification = radar_jobs.classify_postings(postings)
            job_signals = {}
            for bucket, count in classification["counts"].items():
                if count > 0:
                    prior_first_seen = existing_job_signals.get(bucket, {}).get("firstSeenDate")
                    job_signals[bucket] = {"firstSeenDate": prior_first_seen or today.isoformat(), "count": count}
            # buckets that dropped to 0 postings fall out of job_signals
            # entirely -- the role was filled or pulled, so its kernel
            # stops contributing; if a same-titled role reopens later it
            # gets a fresh firstSeenDate, which is correct (we're
            # re-observing a new instance of preparation, not the old one).

    scan_count = existing_schedule.get("scanCount", 0)
    last_scan_at = _parse_date(existing_schedule.get("lastScanAt"))
    advance_scan = entry_source in ("backfill", "scan-runner")
    low_score_streak = existing_radar.get("lowScoreStreak", 0)

    # Most recent Stage 1 screen -- the source for F1/F3/F4 timing signals
    # and the growth tier (radar_timing_signals.py). `company.latestScreen.
    # date` already points at it (firestore_push.py denormalizes this on
    # every screen write, screen doc ids ARE their date) -- fetching that
    # one document directly avoids an order_by("__name__", DESCENDING) query
    # on the screens subcollection, which needs a composite index Firestore
    # doesn't auto-create for descending __name__ ordering. One doc get,
    # not a query, so nothing to index.
    latest_screen = None
    latest_screen_date = (existing.get("latestScreen") or {}).get("date")
    if latest_screen_date:
        screen_doc = company_ref.collection("screens").document(latest_screen_date).get()
        if screen_doc.exists:
            latest_screen = screen_doc.to_dict() or {}
            latest_screen.setdefault("date", latest_screen_date)

    radar_data = compute_radar_state(
        fields, tier1_index, headcount, headcount_checked_at,
        last_scan_at, scan_count, today, advance_scan,
        headcount_growth=headcount_growth, job_signals=job_signals,
        low_score_streak=low_score_streak, watch_floor=watch_floor,
        partner_index=partner_index, latest_screen=latest_screen,
        cost_per_head_overrides=cost_per_head_overrides,
    )
    radar_data["entrySource"] = entry_source
    radar_data["jobSignals"] = job_signals
    if ats:
        radar_data["ats"] = ats

    # Auto-drop-from-view: stamp once, never touch again once set -- a
    # human restores it by hand (no automatic un-drop on a later score
    # recovery this pass; see this module's own docstring).
    if already_dropped:
        radar_data["droppedAt"] = already_dropped
        radar_data["dropReason"] = existing_radar.get("dropReason")
    elif radar_data.get("lowScoreStreak", 0) >= DROP_STREAK_THRESHOLD:
        radar_data["droppedAt"] = today.isoformat()
        radar_data["dropReason"] = f"heatPoints below watch floor ({watch_floor}) for {DROP_STREAK_THRESHOLD} consecutive scans"

    # §9's calibration loop starts here -- log every REAL scan's prediction
    # (not attio-import's cheap recompute) so an outcome months from now has
    # something to score against. See radar_calibration.py's own docstring
    # on why this can't tell you anything yet and why that's not a reason
    # to skip it.
    if advance_scan:
        radar_calibration.log_prediction(db, slug, radar_data, fields.get("roundDate"), today)

    write = {"radar": radar_data}
    # Additive `tags` (2026-07-28) -- same mechanism firestore_push.py's
    # push_company_screen_firestore uses for the `qualified` tag on a
    # gate-cleared screen. A company that passes the mandate screen shows up
    # on the Radar tab via this tag REGARDLESS of its actual `stage` (see
    # hub-next's radar/page.jsx, which now ORs stage=='radar' with
    # tags.includes('radar')) -- so a company can sit in Pipeline as its real
    # working stage and still show up on Radar as a "watch for the next
    # round" signal at the same time, which is the whole point of the tag
    # model over the old single-stage exclusivity.
    if radar_data["mandate"]["pass"]:
        if radar_data.get("droppedAt") and not already_dropped:
            # Just crossed the drop threshold THIS scan -- pull the tag so a
            # tag-only company (not literally stage=='radar') stops
            # surfacing immediately. A company whose real `stage` IS
            # 'radar' can't lose that stage via a tag op -- hub-next's
            # radar/page.jsx filter (keyed off radar.droppedAt directly) is
            # what actually hides those.
            write["tags"] = firestore.ArrayRemove(["radar"])
        elif not radar_data.get("droppedAt"):
            write["tags"] = firestore.ArrayUnion(["radar"])
    company_ref.set(write, merge=True)
    return radar_data
