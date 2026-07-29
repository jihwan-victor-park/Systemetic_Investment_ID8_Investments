"""Prediction logging + scoring -- RADAR_SIGNAL_ENGINE.md §9's calibration
loop, the piece that turns Radar from "a pile of opinions in a table" into
an improving asset. Oscar, 2026-07-29, in response to being told the
hand-set priors (x3.0 for hypergrowth, 8mo cadence, etc.) are unvalidated
and there's no feedback loop: "build solutions for these."

The honest framing, stated once here rather than caveated everywhere else:
NOTHING in this module can be calibrated on day one. Its entire value is in
starting the log now, because RADAR_SIGNAL_ENGINE.md §9 is explicit that
"every month of delay is a permanently lost month of training data." A
prediction logged today is worth nothing until an outcome resolves it,
which takes months by construction (P180's own horizon). This is not a
shortcut around needing real data -- it IS the mechanism that eventually
produces real data, and there is no faster path.

Every real scan (backfill/scan-runner, not the cheap attio-import
recompute) logs its full feature vector. When an outcome becomes known --
a new round gets tracked for the company (F5 confirmation, the same signal
RADAR_PLAN.md already treats as authoritative), or a prediction's window
has been closed long enough with nothing to show for it -- score_prediction
resolves it into a hit/miss and a Brier score contribution.
"""
from datetime import date

WINDOW_HIT_TOLERANCE_DAYS = 45  # a raise within ~6 weeks of the predicted window counts as a hit -- matches contactByDate's own 3-month lead ahead of the window
PENDING_HORIZON_DAYS = 180  # don't call a no-raise-yet prediction a miss before P180's own horizon has actually elapsed -- "too early to tell" is a real state, not a miss


def build_prediction_record(radar_data, round_date_at_prediction=None, today=None):
    """Pure. Extracts the feature vector worth keeping from one scan's
    radar_data (compute_radar_state's return) -- everything §9 needs to
    later ask "was this prediction right, and which input made it wrong."
    Returns None for a mandate-fail scan (nothing was predicted).

    `round_date_at_prediction`: the company's roundDate AS OF this scan --
    stored so sweep_confirmations() can later tell "a new round happened
    since this prediction" apart from "nothing's changed" by comparing
    against the company's current roundDate, with no separate F5/filing
    sensor needed (RADAR_PLAN.md's own Clock 1 isn't built yet)."""
    today = today or date.today()
    hazard = radar_data.get("hazard")
    clock = radar_data.get("clock")
    if not hazard or not clock:
        return None
    return {
        "date": today.isoformat(),
        "p90": hazard["p90"],
        "p180": hazard["p180"],
        "heatPoints": hazard["heatPoints"],
        "confidence": hazard["confidence"],
        "familiesActive": hazard["familiesActive"],
        "growthTier": hazard.get("growthTier"),
        "distressFlag": hazard.get("distressFlag", False),
        "predictedWindowOpen": clock.get("predictedWindowOpen"),
        "windowBasis": clock.get("windowBasis"),
        "roundDateAtPrediction": round_date_at_prediction,
        "outcome": None,  # filled in by score_prediction once an outcome is known
    }


def score_prediction(prediction, actual_round_date, today=None):
    """Pure. `actual_round_date`: the confirmed next round's close date, or
    None to check whether enough time has passed to call an unconfirmed
    prediction a miss. Returns a NEW dict (never mutates `prediction`) with
    `outcome` in {"hit", "miss", "pending", "unscoreable"} and, once
    resolved, `brier`/`daysError`.

    Brier score = (predicted_probability - actual_outcome)^2, the standard
    calibration metric RADAR_SIGNAL_ENGINE.md §9 names explicitly. 0 is a
    perfect prediction, 1 is maximally wrong, 0.25 is what a coin flip
    scores against a 50% prediction."""
    today = today or date.today()
    window_open = prediction.get("predictedWindowOpen")
    p180 = prediction["p180"]

    if actual_round_date is None:
        if not window_open:
            return {**prediction, "outcome": "unscoreable"}  # no window was ever predicted -- nothing to check a miss against
        days_since_window = (today - date.fromisoformat(window_open)).days
        if days_since_window < PENDING_HORIZON_DAYS:
            return {**prediction, "outcome": "pending"}  # too early to call -- not yet a miss
        hit, days_error = False, None
    else:
        window_open_date = date.fromisoformat(window_open) if window_open else None
        days_error = (actual_round_date - window_open_date).days if window_open_date else None
        hit = days_error is not None and abs(days_error) <= WINDOW_HIT_TOLERANCE_DAYS

    brier = round((p180 - (1.0 if hit else 0.0)) ** 2, 4)
    return {**prediction, "outcome": "hit" if hit else "miss", "brier": brier, "daysError": days_error}


def log_prediction(db, slug, radar_data, round_date_at_prediction=None, today=None):
    """Appends one prediction record to companies/{slug}/predictions/{date}.
    Called from radar_state.recompute_and_write on real scans only
    (backfill/scan-runner) -- an opportunistic attio-import recompute isn't
    a new prediction, same distinction advance_scan already draws for
    scanCount. Same-day re-scan overwrites, matching firestore_push.py's
    own same-day-replace convention for screens."""
    record = build_prediction_record(radar_data, round_date_at_prediction, today)
    if record is None:
        return None
    db.collection("companies").document(slug).collection("predictions").document(record["date"]).set(record, merge=True)
    return record


def list_predictions(db, slug):
    return [d.to_dict() for d in db.collection("companies").document(slug).collection("predictions").stream()]


def score_and_update(db, slug, actual_round_date, today=None):
    """Scores every not-yet-resolved prediction for one company against a
    newly-confirmed round date (or None, to sweep for predictions whose
    window has expired with nothing confirmed) and writes results back.
    Returns the list of newly-scored records. Call this from wherever a
    round gets confirmed -- hub-next's createAdditionalRound is the
    existing F5 signal, see this module's own docstring."""
    scored = []
    for record in list_predictions(db, slug):
        if record.get("outcome") not in (None, "pending"):
            continue  # already resolved -- never re-score against a later round
        result = score_prediction(record, actual_round_date, today)
        if result["outcome"] in ("pending", "unscoreable"):
            continue
        db.collection("companies").document(slug).collection("predictions").document(record["date"]).set(result, merge=True)
        scored.append(result)
    return scored


def sweep_confirmations(db):
    """Finds every company with unresolved predictions and checks whether
    a new round has been confirmed since -- by comparing each prediction's
    own `roundDateAtPrediction` snapshot against the company's CURRENT
    `roundDate`. A change means a new round was tracked (hub-next's
    TrackNewRoundForm/createAdditionalRound, or a later Attio import) --
    that IS the F5 confirmation signal RADAR_PLAN.md's own filing-feed
    sensor (Clock 1) would otherwise provide, and it needs no new sensor
    since roundDate is already tracked for every other reason.

    Run this periodically (same cadence as radar_backfill, or its own
    schedule) -- there's no live trigger wiring it to the moment a round
    gets tracked, by design: this stays a batch sweep, same convention as
    every other Radar cron-shaped script in this codebase, rather than a
    new webhook from hub-next into Python.

    Returns {slug: [scored records]} for every company where something
    resolved this sweep."""
    resolved = {}
    slugs_with_predictions = {
        doc.reference.parent.parent.id
        for doc in db.collection_group("predictions").stream()
    }
    for slug in slugs_with_predictions:
        company_doc = db.collection("companies").document(slug).get()
        if not company_doc.exists:
            continue
        current_round_date = (company_doc.to_dict() or {}).get("roundDate")

        pending = [
            p for p in list_predictions(db, slug)
            if p.get("outcome") in (None, "pending")
        ]
        if not pending:
            continue

        # A round is "confirmed since" a given prediction only if the
        # company's current roundDate is BOTH different from and LATER
        # than what that specific prediction saw -- an unrelated field edit
        # that didn't actually change the round must not manufacture a hit.
        newly_confirmed = [
            p for p in pending
            if current_round_date and current_round_date != p.get("roundDateAtPrediction")
            and (not p.get("roundDateAtPrediction") or current_round_date > p["roundDateAtPrediction"])
        ]
        actual_date = date.fromisoformat(current_round_date) if newly_confirmed and current_round_date else None
        scored = score_and_update(db, slug, actual_date)
        if scored:
            resolved[slug] = scored
    return resolved


def calibration_report(db):
    """Project-wide Brier score and hit rate across every resolved
    prediction -- RADAR_SIGNAL_ENGINE.md §9's "is watching this list better
    than watching randomly" business question. Returns a message instead of
    numbers until something has actually resolved, which takes months by
    construction (PENDING_HORIZON_DAYS) -- an empty report here is the
    expected state for a long time, not a bug to fix."""
    all_predictions = [d.to_dict() for d in db.collection_group("predictions").stream()]
    scored = [p for p in all_predictions if p.get("outcome") in ("hit", "miss")]
    if not scored:
        return {
            "totalPredictions": len(all_predictions), "scored": 0,
            "message": "nothing has resolved yet -- expected for months, see this module's own docstring",
        }
    hits = [p for p in scored if p["outcome"] == "hit"]
    briers = [p["brier"] for p in scored if p.get("brier") is not None]
    return {
        "totalPredictions": len(all_predictions),
        "scored": len(scored),
        "hitRate": round(len(hits) / len(scored), 3),
        "meanBrierScore": round(sum(briers) / len(briers), 4) if briers else None,
    }


def main():
    import argparse
    import json
    from google.cloud import firestore
    from . import config
    ap = argparse.ArgumentParser(description="Radar calibration: sweep for confirmed/expired predictions, then report.")
    ap.add_argument("--sweep", action="store_true", help="check for newly-confirmed or expired predictions before reporting")
    args = ap.parse_args()
    db = firestore.Client(project=config.GCP_PROJECT_ID)
    if args.sweep:
        resolved = sweep_confirmations(db)
        print(f"Resolved {sum(len(v) for v in resolved.values())} predictions across {len(resolved)} companies.")
        for slug, records in resolved.items():
            for r in records:
                print(f"  {slug}: {r['date']} -> {r['outcome']} (brier {r['brier']})")
    print(json.dumps(calibration_report(db), indent=2))


if __name__ == "__main__":
    main()
