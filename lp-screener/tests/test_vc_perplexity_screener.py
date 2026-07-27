"""Unit test for the argv-parsing bug fix in vc_perplexity_screener.py
(sys.argv[3]/[4] was read instead of [1]/[2] -- threw IndexError with the
documented number of CLI args). lp-screener/ has no __init__.py (hyphenated
dir name, not a valid package identifier), so import it by adding this
directory to sys.path directly rather than via a package-relative import."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vc_perplexity_screener import DEFAULT_INPUT_CSV, DEFAULT_OUTPUT_CSV, parse_args  # noqa: E402


def test_no_args_uses_defaults():
    assert parse_args(["script.py"]) == (DEFAULT_INPUT_CSV, DEFAULT_OUTPUT_CSV)


def test_one_positional_arg_sets_input_csv_only():
    assert parse_args(["script.py", "in.csv"]) == ("in.csv", DEFAULT_OUTPUT_CSV)


def test_two_positional_args_set_both():
    # This is exactly the case that used to throw IndexError: the documented
    # `python vc_perplexity_screener.py in.csv out.csv` invocation.
    assert parse_args(["script.py", "in.csv", "out.csv"]) == ("in.csv", "out.csv")
