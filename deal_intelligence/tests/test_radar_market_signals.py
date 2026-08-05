"""Unit tests for radar_market_signals.py -- the Perplexity call is
monkeypatched (same convention as test_radar_jobs.py's mocked session), so
these run instantly with no network/API key."""
from deal_intelligence import radar_market_signals as rms


def _fake_response(content, citations=None):
    return lambda *a, **k: (content, citations or [])


class TestResearch:
    def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.setattr(rms.config, "PERPLEXITY_API_KEY", None)
        assert rms.research("Acme", "acme.co", "a widget company") is None

    def test_parses_valid_json_response(self, monkeypatch):
        monkeypatch.setattr(rms.config, "PERPLEXITY_API_KEY", "fake-key")
        monkeypatch.setattr(rms, "perplexity", _fake_response(
            '{"newsVolume": "high", "newsEvidence": "3 TechCrunch articles, https://techcrunch.com/x",'
            ' "publicMomentum": "strong", "momentumEvidence": "hiring surge, https://example.com/y",'
            ' "valuationStepUp": "up", "valuationEvidence": "2x step-up, https://example.com/z",'
            ' "websiteTrafficTrend": "unknown", "trafficEvidence": ""}',
            citations=["https://techcrunch.com/x"],
        ))
        result = rms.research("Acme", "acme.co", "a widget company")
        assert result["newsVolume"] == "high"
        assert result["publicMomentum"] == "strong"
        assert result["valuationStepUp"] == "up"
        # "unknown" from the model normalizes to None, the same
        # missing-not-zero convention every other Radar signal uses.
        assert result["websiteTrafficTrend"] is None
        assert result["citations"] == ["https://techcrunch.com/x"]

    def test_unknown_values_normalize_to_none_not_a_string(self, monkeypatch):
        monkeypatch.setattr(rms.config, "PERPLEXITY_API_KEY", "fake-key")
        monkeypatch.setattr(rms, "perplexity", _fake_response(
            '{"newsVolume": "unknown", "publicMomentum": "unknown", '
            '"valuationStepUp": "unknown", "websiteTrafficTrend": "unknown"}',
        ))
        result = rms.research("Acme", "acme.co", "a widget company")
        assert result["newsVolume"] is None
        assert result["publicMomentum"] is None
        assert result["valuationStepUp"] is None
        assert result["websiteTrafficTrend"] is None

    def test_garbage_value_normalizes_to_none_rather_than_raising(self, monkeypatch):
        # A model hallucinating an out-of-schema value must degrade to
        # missing, not crash the caller or silently pass through junk.
        monkeypatch.setattr(rms.config, "PERPLEXITY_API_KEY", "fake-key")
        monkeypatch.setattr(rms, "perplexity", _fake_response('{"newsVolume": "extremely high"}'))
        result = rms.research("Acme", "acme.co", "a widget company")
        assert result["newsVolume"] is None

    def test_unparseable_response_returns_none(self, monkeypatch):
        monkeypatch.setattr(rms.config, "PERPLEXITY_API_KEY", "fake-key")
        monkeypatch.setattr(rms, "perplexity", _fake_response("not json at all"))
        assert rms.research("Acme", "acme.co", "a widget company") is None

    def test_network_exception_returns_none_not_raises(self, monkeypatch):
        monkeypatch.setattr(rms.config, "PERPLEXITY_API_KEY", "fake-key")

        def _raise(*a, **k):
            raise ConnectionError("boom")
        monkeypatch.setattr(rms, "perplexity", _raise)
        assert rms.research("Acme", "acme.co", "a widget company") is None
