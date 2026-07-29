"""Unit tests for radar_calibration.py's pure prediction/scoring math.
Fabricated inputs, zero mocking, no Firestore -- log_prediction/
list_predictions/score_and_update/sweep_confirmations are thin I/O wrappers
exercised for real by radar_backfill.py against the emulator, same
convention as radar_signal_series.py's own test file."""
from datetime import date

from deal_intelligence import radar_calibration as rc

HAZARD = {"p90": 0.12, "p180": 0.24, "heatPoints": 24.0, "confidence": "medium",
          "familiesActive": ["F3"], "growthTier": "hypergrowth", "distressFlag": False}
CLOCK = {"predictedWindowOpen": "2027-01-12", "windowBasis": "cadence"}


def test_build_prediction_record_extracts_the_feature_vector():
    record = rc.build_prediction_record({"hazard": HAZARD, "clock": CLOCK}, "2026-05-01", today=date(2026, 7, 29))
    assert record["p180"] == 0.24
    assert record["heatPoints"] == 24.0
    assert record["growthTier"] == "hypergrowth"
    assert record["predictedWindowOpen"] == "2027-01-12"
    assert record["roundDateAtPrediction"] == "2026-05-01"
    assert record["outcome"] is None


def test_build_prediction_record_none_on_mandate_fail():
    assert rc.build_prediction_record({"hazard": None, "clock": None}) is None


def test_score_prediction_hit_within_tolerance():
    prediction = rc.build_prediction_record({"hazard": HAZARD, "clock": CLOCK}, None, today=date(2026, 7, 29))
    result = rc.score_prediction(prediction, actual_round_date=date(2027, 1, 20), today=date(2027, 2, 1))
    assert result["outcome"] == "hit"
    assert result["daysError"] == 8
    assert result["brier"] == round((0.24 - 1.0) ** 2, 4)


def test_score_prediction_miss_outside_tolerance():
    prediction = rc.build_prediction_record({"hazard": HAZARD, "clock": CLOCK}, None, today=date(2026, 7, 29))
    result = rc.score_prediction(prediction, actual_round_date=date(2027, 6, 1), today=date(2027, 6, 5))
    assert result["outcome"] == "miss"
    assert result["brier"] == round((0.24 - 0.0) ** 2, 4)


def test_score_prediction_pending_before_the_horizon():
    prediction = rc.build_prediction_record({"hazard": HAZARD, "clock": CLOCK}, None, today=date(2026, 7, 29))
    # Window opened 2027-01-12; only ~30 days later, well under the 180-day pending horizon.
    result = rc.score_prediction(prediction, actual_round_date=None, today=date(2027, 2, 10))
    assert result["outcome"] == "pending"


def test_score_prediction_miss_after_the_horizon_with_no_raise():
    prediction = rc.build_prediction_record({"hazard": HAZARD, "clock": CLOCK}, None, today=date(2026, 7, 29))
    # 200+ days past the predicted window with nothing confirmed.
    result = rc.score_prediction(prediction, actual_round_date=None, today=date(2027, 8, 1))
    assert result["outcome"] == "miss"
    assert result["daysError"] is None


def test_score_prediction_unscoreable_with_no_window_and_no_raise():
    prediction = rc.build_prediction_record({"hazard": HAZARD, "clock": {"predictedWindowOpen": None, "windowBasis": None}}, None)
    result = rc.score_prediction(prediction, actual_round_date=None, today=date(2027, 8, 1))
    assert result["outcome"] == "unscoreable"


def test_perfect_prediction_scores_zero_brier():
    high_confidence = {**HAZARD, "p180": 1.0}
    prediction = rc.build_prediction_record({"hazard": high_confidence, "clock": CLOCK}, None, today=date(2026, 7, 29))
    result = rc.score_prediction(prediction, actual_round_date=date(2027, 1, 12), today=date(2027, 2, 1))
    assert result["brier"] == 0.0


def test_confidently_wrong_prediction_scores_worse_than_a_hedge():
    confident_wrong = rc.score_prediction(
        rc.build_prediction_record({"hazard": {**HAZARD, "p180": 0.9}, "clock": CLOCK}, None, today=date(2026, 7, 29)),
        actual_round_date=None, today=date(2027, 8, 1),
    )
    hedged_wrong = rc.score_prediction(
        rc.build_prediction_record({"hazard": {**HAZARD, "p180": 0.3}, "clock": CLOCK}, None, today=date(2026, 7, 29)),
        actual_round_date=None, today=date(2027, 8, 1),
    )
    assert confident_wrong["brier"] > hedged_wrong["brier"]
