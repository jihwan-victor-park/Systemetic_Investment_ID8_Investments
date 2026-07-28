"""Unit tests for stage1_fit.py's pure decision logic -- _truthy, _tier, and
_dimension_hard_gate never call Perplexity, so these run instantly and don't
need any API key configured."""
from deal_intelligence.stage1_fit import _dimension_hard_gate, _tier, _truthy


class TestTruthy:
    def test_real_booleans(self):
        assert _truthy(True) is True
        assert _truthy(False) is False

    def test_string_variants_perplexity_actually_returns(self):
        # Perplexity is a text model producing JSON, not a strict
        # function-calling API -- hard_auto_pass/watch_list occasionally come
        # back as these string forms instead of real JSON booleans.
        for v in ("true", "True", "yes", "Y", "1"):
            assert _truthy(v) is True
        for v in ("false", "no", "n", "0", "", "anything else"):
            assert _truthy(v) is False

    def test_numeric_and_missing(self):
        assert _truthy(1) is True
        assert _truthy(0) is False
        assert _truthy(None) is False


class TestTier:
    def test_hard_auto_pass_wins_regardless_of_fit_score(self):
        # A single dimension mis-scored to 1 should never silently auto-kill
        # a deal on its own -- but an *explicit* hard_auto_pass always wins,
        # even over a strong numeric score.
        tier, gate = _tier(fit_score=4.0, hard_auto_pass=True, watch_list=False)
        assert (tier, gate) == ("pass", False)

    def test_hard_auto_pass_beats_watch_list(self):
        # A deal disqualified outright is a Pass, not a "come back at Series
        # B" Watch List, regardless of stage.
        tier, gate = _tier(fit_score=3.8, hard_auto_pass=True, watch_list=True)
        assert (tier, gate) == ("pass", False)

    def test_watch_list_when_not_hard_failed(self):
        tier, gate = _tier(fit_score=3.8, hard_auto_pass=False, watch_list=True)
        assert (tier, gate) == ("watch_list", False)

    def test_strong_go_gate_clears(self):
        tier, gate = _tier(fit_score=3.5, hard_auto_pass=False, watch_list=False)
        assert (tier, gate) == ("strong_go", True)

    def test_go_ic_gate_clears(self):
        tier, gate = _tier(fit_score=3.0, hard_auto_pass=False, watch_list=False)
        assert (tier, gate) == ("go_ic", True)

    def test_more_diligence_does_not_clear_gate(self):
        tier, gate = _tier(fit_score=2.5, hard_auto_pass=False, watch_list=False)
        assert (tier, gate) == ("more_diligence", False)

    def test_below_every_threshold_is_a_plain_pass(self):
        tier, gate = _tier(fit_score=1.0, hard_auto_pass=False, watch_list=False)
        assert (tier, gate) == ("pass", False)


class TestDimensionHardGate:
    def test_ai_score_floored_at_one_triggers_the_gate(self):
        reason = _dimension_hard_gate({"ai_score": 1.0, "lead_round_dynamics": 4.0})
        assert "AI" in reason
        assert "[code-enforced gate]" in reason

    def test_lead_round_dynamics_floored_at_one_triggers_the_gate(self):
        reason = _dimension_hard_gate({"ai_score": 4.0, "lead_round_dynamics": 1.0})
        assert "access path" in reason

    def test_no_gate_when_neither_dimension_is_floored(self):
        assert _dimension_hard_gate({"ai_score": 2.0, "lead_round_dynamics": 1.5}) == ""

    def test_a_weak_but_not_floored_ai_score_does_not_trigger(self):
        # 1.3 means at least one subcategory scored above 1 -- the whole
        # dimension didn't bottom out, so this must not force a hard-pass.
        assert _dimension_hard_gate({"ai_score": 1.3}) == ""

    def test_missing_dimensions_do_not_trigger(self):
        assert _dimension_hard_gate({}) == ""
