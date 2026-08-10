"""Regression tests for /process's admission queue.

Two Drive drops land seconds apart every week (PitchBook + Top 10), so n8n
fires two intake flows almost simultaneously. Until 2026-08-10 the second one
got an instant 409 "already running" and its whole weekly run was lost -- see
the note in _start_pipeline. These tests pin the two properties that fix
depends on: a colliding caller QUEUES rather than being rejected, and the slot
is always handed back so one bad run can't wedge the endpoint permanently.

Same import pattern as test_app_helpers.py -- pipeline/ has no __init__.py.
"""
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_slot(monkeypatch):
    """Each test gets its own free slot, so ordering can't leak between them."""
    monkeypatch.setattr(app, "_pipeline_slot", threading.BoundedSemaphore(1))
    monkeypatch.setattr(app, "_pipeline_state", {"status": "idle"})
    yield


def _post(flow_route, monkeypatch=None):
    """Drive _start_pipeline through Flask with a dummy upload."""
    with app.app.test_request_context(
        "/process", method="POST", data=b"xlsx-bytes",
        content_type="application/octet-stream",
    ):
        return app._start_pipeline(stage="Qualified", source="t", flow=flow_route)


def test_second_caller_queues_instead_of_409(monkeypatch):
    """The regression itself: two overlapping runs must BOTH be served."""
    started = []
    release_first = threading.Event()

    def slow_worker(file_bytes, stage, source, top10, source_key, run_state):
        started.append(source_key)
        if source_key == "first":
            release_first.wait(timeout=10)
        with app._pipeline_lock:
            run_state.update({"status": "complete", "created": 1, "deals": []})

    monkeypatch.setattr(app, "_run_pipeline_worker", slow_worker)

    results = {}

    def call(name):
        body, status = _unpack(_post(name))
        results[name] = status

    t1 = threading.Thread(target=call, args=("first",))
    t1.start()
    while "first" not in started:            # ensure the slot is genuinely taken
        time.sleep(0.01)

    t2 = threading.Thread(target=call, args=("second",))
    t2.start()
    time.sleep(0.2)
    assert "second" not in started, "second run should be waiting, not running"
    assert results.get("second") is None, "second run should not have returned yet"

    release_first.set()
    t1.join(timeout=15)
    t2.join(timeout=15)

    assert results["first"] == 200
    assert results["second"] == 200, "the colliding run must be served, not 409'd"
    assert started == ["first", "second"], "runs must be serialized, never concurrent"


def test_slot_is_released_when_the_worker_crashes(monkeypatch):
    """A crashed run must not wedge every later run behind a dead slot."""
    def exploding_worker(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(app, "_run_pipeline_worker", exploding_worker)
    _, status = _unpack(_post("first"))
    assert status == 500

    # The slot must be free again immediately.
    assert app._pipeline_slot.acquire(timeout=2), "slot was stranded by the crash"
    app._pipeline_slot.release()


def test_busy_past_the_wait_window_is_503_not_409(monkeypatch):
    """Giving up is still possible -- it just takes _QUEUE_WAIT_SECONDS, and it
    reports 503 (try again) rather than 409 (your request was wrong)."""
    monkeypatch.setattr(app, "_QUEUE_WAIT_SECONDS", 0.1)
    app._pipeline_slot.acquire()             # simulate a run already in flight
    try:
        body, status = _unpack(_post("second"))
        assert status == 503
        assert "busy" in body.get_json()["error"]
    finally:
        app._pipeline_slot.release()


def _unpack(rv):
    """_start_pipeline returns either a Response or a (Response, status) tuple."""
    if isinstance(rv, tuple):
        return rv[0], rv[1]
    return rv, rv.status_code
