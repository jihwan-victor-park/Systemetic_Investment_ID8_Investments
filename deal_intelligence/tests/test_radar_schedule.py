"""Unit tests for radar_schedule.py's pure scan-scheduling math -- no
network, no Firestore; everything here runs instantly."""
from datetime import date

from deal_intelligence import radar_schedule as rs


def test_shift_out_of_dead_zone_august_later():
    assert rs.shift_out_of_dead_zone(date(2026, 8, 12), "later") == date(2026, 9, 5)


def test_shift_out_of_dead_zone_august_earlier():
    assert rs.shift_out_of_dead_zone(date(2026, 8, 12), "earlier") == date(2026, 7, 15)


def test_shift_out_of_dead_zone_year_end_later_crosses_new_year():
    assert rs.shift_out_of_dead_zone(date(2026, 12, 22), "later") == date(2027, 1, 12)


def test_shift_out_of_dead_zone_year_end_earlier_stays_same_year():
    assert rs.shift_out_of_dead_zone(date(2026, 12, 22), "earlier") == date(2026, 12, 5)


def test_shift_out_of_dead_zone_early_january_is_still_the_year_end_zone():
    # 3 Jan is inside the "roughly 15 Dec - 6 Jan" zone even though it's a
    # new calendar year -- "earlier" here means the PREVIOUS December.
    assert rs.shift_out_of_dead_zone(date(2027, 1, 3), "earlier") == date(2026, 12, 5)
    assert rs.shift_out_of_dead_zone(date(2027, 1, 3), "later") == date(2027, 1, 12)


def test_shift_out_of_dead_zone_no_shift_outside_any_zone():
    d = date(2026, 3, 15)
    assert rs.shift_out_of_dead_zone(d, "later") == d
    assert rs.shift_out_of_dead_zone(d, "earlier") == d


def test_next_mandatory_sweep_picks_the_nearer_upcoming_date():
    assert rs.next_mandatory_sweep(date(2026, 6, 1)) == date(2026, 9, 5)
    assert rs.next_mandatory_sweep(date(2026, 10, 1)) == date(2027, 1, 12)


def test_next_mandatory_sweep_on_the_date_itself():
    assert rs.next_mandatory_sweep(date(2026, 9, 5)) == date(2026, 9, 5)


def test_opening_sequence_scan_1_at_t_plus_4_months():
    assert rs.opening_sequence_scan(date(2026, 2, 10), scan_count=0) == date(2026, 6, 10)


def test_opening_sequence_scan_2_at_t_plus_6_months():
    assert rs.opening_sequence_scan(date(2026, 2, 10), scan_count=1) == date(2026, 8, 10)


def test_opening_sequence_returns_none_once_both_scans_done():
    assert rs.opening_sequence_scan(date(2026, 2, 10), scan_count=2) is None


def test_opening_sequence_returns_none_without_a_round_date():
    assert rs.opening_sequence_scan(None, scan_count=0) is None


def test_base_interval_weeks_table():
    assert rs.base_interval_weeks(18) == 16
    assert rs.base_interval_weeks(10) == 12
    assert rs.base_interval_weeks(6) == 8
    assert rs.base_interval_weeks(4) == 6
    assert rs.base_interval_weeks(1) == 4


def test_base_interval_weeks_unknown_defaults_to_widest():
    assert rs.base_interval_weeks(None) == 16


def test_apply_modifiers_high_intensity_shortens():
    assert rs.apply_modifiers(8, "high") == round(8 * 0.7)


def test_apply_modifiers_low_intensity_lengthens():
    assert rs.apply_modifiers(8, "low") == round(8 * 1.4)


def test_apply_modifiers_respects_bounds():
    assert rs.apply_modifiers(1, "high") == 4  # floor
    assert rs.apply_modifiers(100, "low") == 16  # ceiling


def test_apply_modifiers_preparation_signal_caps_at_six_weeks():
    assert rs.apply_modifiers(16, "medium", preparation_signal_active=True) == 6


def test_next_scan_at_uses_opening_sequence_first():
    d, reason = rs.next_scan_at(
        last_scan_at=None, round_date=date(2026, 2, 10), scan_count=0,
        months_until_window=6, capital_intensity="medium", today=date(2026, 6, 5),
    )
    assert d == date(2026, 6, 10)
    assert "opening sequence" in reason


def test_next_scan_at_falls_through_to_adaptive_after_opening_sequence():
    d, reason = rs.next_scan_at(
        last_scan_at=date(2026, 9, 16), round_date=date(2026, 2, 10), scan_count=2,
        months_until_window=6, capital_intensity="high", today=date(2026, 9, 16),
    )
    assert d == date(2026, 9, 16) + __import__("datetime").timedelta(weeks=round(8 * 0.7))
    assert "6 weeks" in reason or "5 weeks" in reason  # round(8*0.7) == 6


def test_next_scan_at_ceiling_is_the_mandatory_sweep_when_it_comes_first():
    # Adaptive interval alone would land well past the sweep date.
    d, reason = rs.next_scan_at(
        last_scan_at=date(2026, 7, 1), round_date=date(2025, 1, 1), scan_count=5,
        months_until_window=20, capital_intensity="low", today=date(2026, 7, 1),
    )
    assert d == date(2026, 9, 5)
    assert "mandatory sweep" in reason


def test_next_scan_at_never_lands_in_a_dead_zone():
    d, reason = rs.next_scan_at(
        last_scan_at=date(2026, 7, 20), round_date=date(2025, 1, 1), scan_count=5,
        months_until_window=4, capital_intensity="medium", today=date(2026, 7, 20),
    )
    # 6-week adaptive interval from 20 Jul lands 31 Aug -- inside the August
    # dead zone -- so it must get shifted to 5 Sep.
    assert d == date(2026, 9, 5)
    assert "dead zone" in reason
