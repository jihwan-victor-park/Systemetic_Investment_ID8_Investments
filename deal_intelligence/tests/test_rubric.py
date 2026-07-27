"""Unit tests for rubric.py's pure scoring math -- dimension_score/
weighted_score/raw_score never touch the network, so these run instantly."""
from deal_intelligence import rubric


def test_dimension_score_averages_to_one_decimal():
    assert rubric.dimension_score([1, 2, 4]) == 2.3


def test_dimension_score_drops_falsy_scores_instead_of_treating_as_zero():
    # A subcategory the model dropped is simply absent, not defaulted to 0 --
    # see dimension_score's own docstring for why (a partial response
    # shouldn't unfairly tank the dimension).
    assert rubric.dimension_score([4, None, 0]) == 4.0


def test_dimension_score_empty_list_is_zero_not_an_error():
    assert rubric.dimension_score([]) == 0.0


def test_weighted_score_is_a_plain_mean_at_v4_equal_weights():
    param_scores = {p["key"]: score for p, score in zip(rubric.PARAMS, [1, 2, 3, 4, 2, 3])}
    assert rubric.weighted_score(param_scores) == 2.5


def test_weighted_score_missing_dimension_counts_as_zero():
    # weighted_score always divides by the full dimension count (len(PARAMS)),
    # so a dimension key absent from param_scores drags the average down --
    # this pins that behavior so a future caller doesn't assume missing ==
    # "excluded from the mean".
    only_one = {rubric.PARAMS[0]["key"]: 4}
    expected = round(4 / len(rubric.PARAMS), 1)
    assert rubric.weighted_score(only_one) == expected


def test_raw_score_matches_weighted_score_at_v4_equal_weights():
    param_scores = {p["key"]: 3 for p in rubric.PARAMS}
    assert rubric.raw_score(param_scores) == rubric.weighted_score(param_scores)


def test_validate_passes_on_the_real_params():
    assert rubric.validate() is True


def test_every_dimension_has_the_expected_v4_weight():
    # All six dimensions at exact parity (100/6 each) -- Terms is no longer
    # gate-only/zero-weight, per rubric.py's own v4 module docstring.
    assert len(rubric.PARAMS) == 6
    keys = {p["key"] for p in rubric.PARAMS}
    assert keys == {
        "lead_round_dynamics", "founder_team_quality", "ai_score",
        "terms", "fundamentals", "return_potential",
    }
