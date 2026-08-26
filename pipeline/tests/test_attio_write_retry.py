"""Unit tests for pipeline/app.py's Attio write-retry helpers.

_attio_write_retry replaced the old POST-only _attio_post_retry on 2026-08-26
so that PATCH writes get the same 5xx protection a create already had. The
cases that matter are the ones that were silently losing writes before:

  * a transient 5xx followed by a success  -> the write lands
  * a 4xx                                  -> returned immediately, NOT retried
                                              (a validation error a retry can't fix,
                                              and retrying would triple the latency
                                              of every genuinely-bad row)
  * every attempt 5xx                      -> the last response is RETURNED, not
                                              raised, so callers keep their
                                              existing status-code branches
  * every attempt a network error          -> raises, since there is no response
                                              to hand back

Same import pattern as test_app_helpers.py: pipeline/ has no __init__.py, so
add this directory to sys.path and import `app` directly. No credentials are
needed -- requests is monkeypatched, so nothing leaves the process.
"""
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, text="", json_body=None):
        self.status_code = status_code
        self.text = text
        self._json = json_body or {}

    def json(self):
        return self._json


class RecordingSender:
    """Stands in for requests.post / requests.patch and replays a script of
    outcomes. An outcome is either a FakeResponse or an exception to raise."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        outcome = self.outcomes.pop(0) if self.outcomes else FakeResponse(200)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """The helper backs off 2s then 4s between attempts. Tests assert on call
    counts, not on wall-clock behaviour, so drop the sleeps entirely."""
    monkeypatch.setattr(app.time, "sleep", lambda _seconds: None)


@pytest.fixture(autouse=True)
def stub_attio_headers(monkeypatch):
    """attio_headers() reads the module-level ATTIO_API_KEY. Stub it so the
    tests never depend on a key being present, and so a real key can never be
    picked up from the environment during a test run."""
    monkeypatch.setattr(app, "attio_headers", lambda: {"Authorization": "Bearer test"})


@pytest.mark.parametrize("method", ["post", "patch"])
class TestAttioWriteRetry:
    def test_succeeds_first_try_without_retrying(self, monkeypatch, method):
        sender = RecordingSender(FakeResponse(200))
        monkeypatch.setattr(requests, method, sender)

        resp = app._attio_write_retry(method, "https://attio.test/x", {"a": 1})

        assert resp.status_code == 200
        assert len(sender.calls) == 1

    def test_retries_a_transient_5xx_then_succeeds(self, monkeypatch, method):
        sender = RecordingSender(FakeResponse(500, "boom"), FakeResponse(201))
        monkeypatch.setattr(requests, method, sender)

        resp = app._attio_write_retry(method, "https://attio.test/x", {"a": 1})

        assert resp.status_code == 201
        assert len(sender.calls) == 2

    def test_does_not_retry_a_4xx(self, monkeypatch, method):
        # A 400 is a validation problem -- retrying cannot fix it, and doing so
        # would multiply the cost of every bad row in a large intake file.
        sender = RecordingSender(FakeResponse(400, "bad slug"))
        monkeypatch.setattr(requests, method, sender)

        resp = app._attio_write_retry(method, "https://attio.test/x", {"a": 1})

        assert resp.status_code == 400
        assert len(sender.calls) == 1

    def test_exhausted_5xx_returns_the_last_response_rather_than_raising(
        self, monkeypatch, method
    ):
        # Callers branch on status_code; raising here would turn a handled Attio
        # outage into an unhandled traceback partway through a run.
        sender = RecordingSender(
            FakeResponse(500), FakeResponse(502), FakeResponse(503, "still down")
        )
        monkeypatch.setattr(requests, method, sender)

        resp = app._attio_write_retry(method, "https://attio.test/x", {"a": 1})

        assert resp.status_code == 503
        assert len(sender.calls) == 3

    def test_retries_a_network_error_then_succeeds(self, monkeypatch, method):
        sender = RecordingSender(
            requests.ConnectionError("reset by peer"), FakeResponse(200)
        )
        monkeypatch.setattr(requests, method, sender)

        resp = app._attio_write_retry(method, "https://attio.test/x", {"a": 1})

        assert resp.status_code == 200
        assert len(sender.calls) == 2

    def test_exhausted_network_errors_raise(self, monkeypatch, method):
        # No response was ever received, so there is nothing to return. The
        # callers on the intake and hub-edit paths catch RequestException.
        sender = RecordingSender(
            requests.ConnectionError("1"),
            requests.ConnectionError("2"),
            requests.ConnectionError("3"),
        )
        monkeypatch.setattr(requests, method, sender)

        with pytest.raises(requests.RequestException):
            app._attio_write_retry(method, "https://attio.test/x", {"a": 1})

        assert len(sender.calls) == 3

    def test_forwards_url_headers_and_body_unchanged(self, monkeypatch, method):
        sender = RecordingSender(FakeResponse(200))
        monkeypatch.setattr(requests, method, sender)
        body = {"data": {"values": {"stage": [{"status": "Qualified"}]}}}

        app._attio_write_retry(method, "https://attio.test/deals/rec_1", body)

        call = sender.calls[0]
        assert call["url"] == "https://attio.test/deals/rec_1"
        assert call["json"] is body
        assert call["headers"] == {"Authorization": "Bearer test"}

    def test_attempts_is_configurable(self, monkeypatch, method):
        sender = RecordingSender(FakeResponse(500), FakeResponse(500))
        monkeypatch.setattr(requests, method, sender)

        app._attio_write_retry(method, "https://attio.test/x", {}, attempts=2)

        assert len(sender.calls) == 2


class TestThinWrappers:
    """_attio_post_retry kept its original name and signature so existing
    callers are untouched; _attio_patch_retry is its PATCH twin. Both must
    dispatch to the correct HTTP verb -- a mix-up here would send a create to
    the update endpoint."""

    def test_post_wrapper_uses_post(self, monkeypatch):
        post = RecordingSender(FakeResponse(201))
        patch = RecordingSender(FakeResponse(200))
        monkeypatch.setattr(requests, "post", post)
        monkeypatch.setattr(requests, "patch", patch)

        app._attio_post_retry("https://attio.test/x", {"a": 1})

        assert len(post.calls) == 1
        assert len(patch.calls) == 0

    def test_patch_wrapper_uses_patch(self, monkeypatch):
        post = RecordingSender(FakeResponse(201))
        patch = RecordingSender(FakeResponse(200))
        monkeypatch.setattr(requests, "post", post)
        monkeypatch.setattr(requests, "patch", patch)

        app._attio_patch_retry("https://attio.test/x", {"a": 1})

        assert len(patch.calls) == 1
        assert len(post.calls) == 0

    def test_post_wrapper_still_retries_5xx(self, monkeypatch):
        # Regression guard: the original _attio_post_retry behaviour (added
        # after the Chai Discovery 500 on 2026-07-20) must survive the
        # refactor into _attio_write_retry.
        post = RecordingSender(FakeResponse(500), FakeResponse(201))
        monkeypatch.setattr(requests, "post", post)

        resp = app._attio_post_retry("https://attio.test/x", {"a": 1})

        assert resp.status_code == 201
        assert len(post.calls) == 2


class TestUpsertDealExistingBranchSurfacesPatchFailure:
    """upsert_deal's existing-deal branch used to return {"status": "existing"}
    no matter what the PATCH did, so a failed write was reported to
    run_pipeline as a healthy re-seen deal and counted into the email. It now
    returns an error string, which run_pipeline routes into results["errors"].
    """

    def _row(self):
        return {"Companies": "Acme", "Series": "Series C"}

    def test_successful_patch_still_reports_existing(self, monkeypatch):
        monkeypatch.setattr(app, "find_deal", lambda name, series: "rec_existing")
        monkeypatch.setattr(app, "get_company_index", lambda *a, **k: {"by_name": {}, "by_domain": {}})
        monkeypatch.setattr(app, "resolve_investor_links", lambda row, index: {})
        monkeypatch.setattr(app, "_attio_patch_retry", lambda url, body: FakeResponse(200))

        result = app.upsert_deal(self._row(), "comp_1", stage="Qualified")

        assert result["status"] == "existing"
        assert result["record_id"] == "rec_existing"

    def test_failed_patch_is_reported_as_an_error(self, monkeypatch):
        monkeypatch.setattr(app, "find_deal", lambda name, series: "rec_existing")
        monkeypatch.setattr(app, "get_company_index", lambda *a, **k: {"by_name": {}, "by_domain": {}})
        monkeypatch.setattr(app, "resolve_investor_links", lambda row, index: {})
        monkeypatch.setattr(
            app, "_attio_patch_retry", lambda url, body: FakeResponse(503, "unavailable")
        )

        result = app.upsert_deal(self._row(), "comp_1", stage="Qualified")

        assert isinstance(result, str)
        assert result.startswith("error:503")

    def test_network_failure_is_reported_as_an_error(self, monkeypatch):
        def boom(url, body):
            raise requests.ConnectionError("no route to host")

        monkeypatch.setattr(app, "find_deal", lambda name, series: "rec_existing")
        monkeypatch.setattr(app, "get_company_index", lambda *a, **k: {"by_name": {}, "by_domain": {}})
        monkeypatch.setattr(app, "resolve_investor_links", lambda row, index: {})
        monkeypatch.setattr(app, "_attio_patch_retry", boom)

        result = app.upsert_deal(self._row(), "comp_1", stage="Qualified")

        assert isinstance(result, str)
        assert result.startswith("error:network:")
