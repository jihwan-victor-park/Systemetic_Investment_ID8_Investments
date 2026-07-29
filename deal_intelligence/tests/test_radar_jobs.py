"""Unit tests for radar_jobs.py. classify_postings is pure (fabricated
inputs, zero mocking); detect_ats/fetch_postings are this module's one
real-I/O surface and get a mocked-session test via pytest's monkeypatch --
the one place in this pass's additions with real I/O to mock, per the
implementation plan's own call-out."""
from deal_intelligence import radar_jobs as rj


class _FakeResponse:
    def __init__(self, ok=True, text="", json_data=None):
        self.ok = ok
        self.text = text
        self._json = json_data

    def json(self):
        return self._json


def test_detect_ats_greenhouse_url_in_html(monkeypatch):
    monkeypatch.setattr(rj.session, "get", lambda *a, **k: _FakeResponse(text='<a href="https://boards.greenhouse.io/northwind">Careers</a>'))
    assert rj.detect_ats("northwind.com") == {"provider": "greenhouse", "token": "northwind"}


def test_detect_ats_lever_url_in_html(monkeypatch):
    monkeypatch.setattr(rj.session, "get", lambda *a, **k: _FakeResponse(text='<a href="https://jobs.lever.co/acme">Careers</a>'))
    assert rj.detect_ats("acme.com") == {"provider": "lever", "token": "acme"}


def test_detect_ats_no_match_returns_none(monkeypatch):
    monkeypatch.setattr(rj.session, "get", lambda *a, **k: _FakeResponse(text="<html>no careers page mentioned</html>"))
    assert rj.detect_ats("quiet-co.com") is None


def test_detect_ats_no_website_returns_none():
    assert rj.detect_ats(None) is None


def test_detect_ats_request_failure_never_raises(monkeypatch):
    def _raise(*a, **k):
        raise ConnectionError("boom")
    monkeypatch.setattr(rj.session, "get", _raise)
    assert rj.detect_ats("flaky.com") is None


def test_detect_ats_non_ok_response_returns_none(monkeypatch):
    monkeypatch.setattr(rj.session, "get", lambda *a, **k: _FakeResponse(ok=False))
    assert rj.detect_ats("gone404.com") is None


def test_fetch_postings_greenhouse_shape(monkeypatch):
    payload = {"jobs": [{"title": "VP Finance", "departments": [{"name": "Finance"}]}]}
    monkeypatch.setattr(rj.session, "get", lambda *a, **k: _FakeResponse(json_data=payload))
    postings = rj.fetch_postings("greenhouse", "northwind")
    assert postings == [{"title": "VP Finance", "department": "Finance", "firstSeen": None}]


def test_fetch_postings_lever_shape(monkeypatch):
    payload = [{"text": "Head of Corp Dev", "categories": {"team": "Corp Dev"}, "createdAt": 1735689600000}]
    monkeypatch.setattr(rj.session, "get", lambda *a, **k: _FakeResponse(json_data=payload))
    postings = rj.fetch_postings("lever", "acme")
    assert postings[0]["title"] == "Head of Corp Dev"
    assert postings[0]["firstSeen"] == "2025-01-01"


def test_fetch_postings_ashby_shape(monkeypatch):
    payload = {"jobs": [{"title": "Recruiter", "department": "People", "publishedAt": "2026-03-05T00:00:00.000Z"}]}
    monkeypatch.setattr(rj.session, "get", lambda *a, **k: _FakeResponse(json_data=payload))
    postings = rj.fetch_postings("ashby", "acme")
    assert postings[0]["firstSeen"] == "2026-03-05"


def test_fetch_postings_unknown_provider_or_no_token_is_empty():
    assert rj.fetch_postings("unknown", "x") == []
    assert rj.fetch_postings("greenhouse", None) == []


def test_fetch_postings_request_failure_never_raises(monkeypatch):
    def _raise(*a, **k):
        raise ConnectionError("boom")
    monkeypatch.setattr(rj.session, "get", _raise)
    assert rj.fetch_postings("greenhouse", "northwind") == []


def test_classify_postings_buckets_by_title_keyword():
    postings = [
        {"title": "VP Finance"},
        {"title": "Head of Corp Dev"},
        {"title": "Senior Backend Engineer"},  # unmatched -- shouldn't land in any bucket
    ]
    result = rj.classify_postings(postings)
    assert result["counts"]["rolesSeniorFinance"] == 1
    assert result["counts"]["rolesCorpDev"] == 1
    assert result["counts"]["rolesExecGTM"] == 0
    assert "Senior Backend Engineer" not in result["allTitlesSeen"]


def test_classify_postings_new_titles_diffs_against_previously_seen():
    postings = [{"title": "VP Finance"}, {"title": "Controller"}]
    result = rj.classify_postings(postings, previously_seen_titles=["VP Finance"])
    assert result["newTitles"]["rolesSeniorFinance"] == ["Controller"]


def test_classify_postings_no_new_titles_when_all_previously_seen():
    postings = [{"title": "VP Finance"}]
    result = rj.classify_postings(postings, previously_seen_titles=["VP Finance"])
    assert result["newTitles"]["rolesSeniorFinance"] == []


def test_classify_postings_case_insensitive_match():
    result = rj.classify_postings([{"title": "chief revenue officer"}])
    assert result["counts"]["rolesExecGTM"] == 1
