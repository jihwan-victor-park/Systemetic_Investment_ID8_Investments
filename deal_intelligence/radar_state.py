"""Radar's orchestrator (RADAR_PLAN.md Parts I/III/IV/VI/VIII) -- the sole
writer of `companies/{slug}.radar`. Ties radar_mandate.screen() +
capital_clock.compute() + radar_schedule.next_scan_at() together.

Seasonality shifting of the clock's raw dates happens HERE, not inside
capital_clock.compute() -- see that module's own docstring for why.
predictedWindowOpen shifts LATER (never predicts a launch into a dead
zone); contactByDate shifts EARLIER (never lets our own deadline chase a
dead zone); alertAtDate is re-derived from the SHIFTED contactByDate, not
capital_clock's raw one.
"""
from datetime import date, timedelta

from google.cloud import firestore

from . import apollo_org, capital_clock, config, radar_mandate, radar_schedule

_db = None
SCHEMA_VERSION = 1
APOLLO_STALENESS_DAYS = 30
CRITICAL_ZONE_MONTHS = 5  # matches radar_schedule.base_interval_weeks' own 3-5mo critical-zone band


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


def compute_radar_state(fields, tier1_index, headcount, headcount_checked_at,
                         last_scan_at, scan_count, today=None, advance_scan=True):
    """Pure orchestration -- no I/O, unit-testable with fabricated inputs.

    fields: {name, hq, series, top10VC, roundSize, roundDate, radarCategory,
    description}. Short-circuits on mandate failure: no clock/schedule
    computed at all, matching Part IV guardrail #1 ("mandatePass = false ->
    no sensing, no escalation, ever").

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
        }

    region = radar_mandate.classify_region(fields.get("hq"))
    clock = capital_clock.compute(
        {"roundSize": fields.get("roundSize"), "roundDate": fields.get("roundDate"), "region": region,
         "radarCategory": fields.get("radarCategory"), "description": fields.get("description"),
         "headcountCheckedAt": headcount_checked_at},
        headcount, today,
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

    next_scan_date, next_scan_reason = radar_schedule.next_scan_at(
        last_scan_at, _parse_date(fields.get("roundDate")), scan_count,
        months_until_window, clock["capitalIntensity"], today,
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
    }


def _is_stale(checked_at, today):
    parsed = _parse_date(checked_at)
    if not parsed:
        return True
    return (today - parsed).days > APOLLO_STALENESS_DAYS


def recompute_and_write(slug, fields, tier1_index, entry_source, db=None, apollo_lookup=None, today=None):
    """The one function both the Attio-import hook and the scan runner call.
    Reads the company's existing radar.clock.headcountCheckedAt off
    Firestore first; only calls Apollo if missing or >30 days stale -- keeps
    the Attio-import hook cheap even on a bulk import, and it's the SAME
    staleness rule the scan runner uses, so the two paths never disagree
    about when a fresh Apollo call is warranted.

    entry_source: 'attio-import' | 'backfill' | 'scan-runner' -- stamped for
    audit, and also decides `advance_scan` (see compute_radar_state):
    'backfill'/'scan-runner' count as a real scan, 'attio-import' does not.

    Writes via `company_ref.set({'radar': {...}}, merge=True)` -- same
    convention as the rest of firestore_push.py."""
    db = db or _firestore()
    apollo_lookup = apollo_lookup or apollo_org.get_org_headcount
    today = today or date.today()

    company_ref = db.collection("companies").document(slug)
    existing = company_ref.get().to_dict() or {}
    existing_radar = existing.get("radar") or {}
    existing_clock = existing_radar.get("clock") or {}
    existing_schedule = existing_radar.get("schedule") or {}

    headcount = existing_clock.get("headcount")
    headcount_checked_at = existing_clock.get("headcountCheckedAt")
    if _is_stale(headcount_checked_at, today):
        domain = fields.get("website") or fields.get("domain")
        result = apollo_lookup(domain) if domain else None
        if result:
            headcount = result["headcount"]
            headcount_checked_at = result["checkedAt"]

    scan_count = existing_schedule.get("scanCount", 0)
    last_scan_at = _parse_date(existing_schedule.get("lastScanAt"))
    advance_scan = entry_source in ("backfill", "scan-runner")

    radar_data = compute_radar_state(
        fields, tier1_index, headcount, headcount_checked_at,
        last_scan_at, scan_count, today, advance_scan,
    )
    radar_data["entrySource"] = entry_source
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
        write["tags"] = firestore.ArrayUnion(["radar"])
    company_ref.set(write, merge=True)
    return radar_data
