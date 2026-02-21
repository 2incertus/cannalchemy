"""Tests for LLM explanation client."""
import json
import time
from unittest.mock import patch, MagicMock

import httpx
import pytest

from cannalchemy.explain.llm import LLMClient


@pytest.fixture
def client():
    return LLMClient(
        primary_url="https://api.z.ai/api/anthropic/v1/messages",
        primary_model="glm-4.7",
        primary_key="test-key",
        fallback_url="http://localhost:11434",
        fallback_model="llama3.2",
    )


@pytest.fixture
def strain_data():
    return {
        "name": "Blue Dream",
        "strain_type": "hybrid",
        "compositions": [
            {"molecule": "myrcene", "percentage": 0.35, "type": "terpene"},
            {"molecule": "limonene", "percentage": 0.28, "type": "terpene"},
            {"molecule": "thc", "percentage": 21.0, "type": "cannabinoid"},
        ],
        "predicted_effects": [
            {"name": "relaxed", "probability": 0.83, "confidence": "high"},
            {"name": "happy", "probability": 0.78, "confidence": "medium"},
        ],
        "pathways": [
            {"molecule": "myrcene", "receptor": "CB1", "ki_nm": 50.0},
        ],
    }


class TestLLMClientInit:
    def test_creates_with_config(self, client):
        assert client.primary_url == "https://api.z.ai/api/anthropic/v1/messages"
        assert client.primary_model == "glm-4.7"
        assert client.fallback_url == "http://localhost:11434"

    def test_creates_without_fallback(self):
        c = LLMClient(
            primary_url="https://api.z.ai/api/anthropic/v1/messages",
            primary_model="glm-4.7",
            primary_key="test-key",
        )
        assert c.fallback_url is None

    def test_creates_from_env(self, monkeypatch):
        monkeypatch.setenv("CANNALCHEMY_LLM_PRIMARY_URL", "https://example.com/v1/messages")
        monkeypatch.setenv("CANNALCHEMY_LLM_PRIMARY_MODEL", "test-model")
        monkeypatch.setenv("CANNALCHEMY_LLM_PRIMARY_KEY", "test-key")
        monkeypatch.setenv("CANNALCHEMY_LLM_FALLBACK_URL", "http://localhost:11434")
        monkeypatch.setenv("CANNALCHEMY_LLM_FALLBACK_MODEL", "llama3.2")
        c = LLMClient.from_env()
        assert c.primary_url == "https://example.com/v1/messages"
        assert c.fallback_model == "llama3.2"

    def test_from_env_returns_none_without_primary(self, monkeypatch):
        monkeypatch.delenv("CANNALCHEMY_LLM_PRIMARY_URL", raising=False)
        monkeypatch.delenv("CANNALCHEMY_LLM_PRIMARY_KEY", raising=False)
        c = LLMClient.from_env()
        assert c is None


class TestLLMClientCalls:
    def test_primary_success(self, client, strain_data):
        """Primary returns text — use it, don't call fallback."""
        with patch.object(client, "_call_primary", return_value="Myrcene drives relaxation.") as mock_p, \
             patch.object(client, "_call_fallback") as mock_f:
            text, provider = client.explain_strain(strain_data)
            assert text == "Myrcene drives relaxation."
            assert provider == "zai"
            mock_p.assert_called_once()
            mock_f.assert_not_called()

    def test_primary_fails_fallback_succeeds(self, client, strain_data):
        """Primary fails — fall back to Ollama."""
        with patch.object(client, "_call_primary", return_value=None), \
             patch.object(client, "_call_fallback", return_value="Relaxing strain."):
            text, provider = client.explain_strain(strain_data)
            assert text == "Relaxing strain."
            assert provider == "ollama"

    def test_both_fail(self, client, strain_data):
        """Both providers fail — return None."""
        with patch.object(client, "_call_primary", return_value=None), \
             patch.object(client, "_call_fallback", return_value=None):
            text, provider = client.explain_strain(strain_data)
            assert text is None
            assert provider is None

    def test_summarize_strain(self, client, strain_data):
        with patch.object(client, "_call_primary", return_value="Relaxing hybrid."):
            text, provider = client.summarize_strain(strain_data)
            assert text == "Relaxing hybrid."
            assert provider == "zai"

    def test_rate_limit_skips_primary(self, client, strain_data):
        """After 429, primary is skipped for 60s."""
        client._rate_limited_until = time.time() + 60
        with patch.object(client, "_call_fallback", return_value="Fallback text."):
            text, provider = client.explain_strain(strain_data)
            assert provider == "ollama"

    def test_no_fallback_configured(self, strain_data):
        """No fallback URL — return None after primary fails."""
        c = LLMClient(
            primary_url="https://example.com/v1/messages",
            primary_model="test",
            primary_key="key",
        )
        with patch.object(c, "_call_primary", return_value=None):
            text, provider = c.explain_strain(strain_data)
            assert text is None


class TestLLMClientHTTP:
    def test_primary_http_success(self, client):
        """Test actual HTTP call format for Anthropic-compatible API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Myrcene drives relaxation via CB1."}]
        }
        with patch("cannalchemy.explain.llm.httpx.post", return_value=mock_response) as mock_post:
            result = client._call_primary("test prompt")
            assert result == "Myrcene drives relaxation via CB1."
            call_kwargs = mock_post.call_args
            assert call_kwargs[0][0] == "https://api.z.ai/api/anthropic/v1/messages"
            assert call_kwargs[1]["headers"]["x-api-key"] == "test-key"
            assert call_kwargs[1]["json"]["model"] == "glm-4.7"

    def test_primary_http_timeout(self, client):
        with patch("cannalchemy.explain.llm.httpx.post", side_effect=httpx.TimeoutException("timeout")):
            result = client._call_primary("test")
            assert result is None

    def test_primary_http_429(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 429
        with patch("cannalchemy.explain.llm.httpx.post", return_value=mock_response):
            result = client._call_primary("test")
            assert result is None
            assert client._rate_limited_until > time.time()

    def test_fallback_http_success(self, client):
        """Test Ollama API call format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "A relaxing indica."}
        with patch("cannalchemy.explain.llm.httpx.post", return_value=mock_response) as mock_post:
            result = client._call_fallback("test prompt")
            assert result == "A relaxing indica."
            call_kwargs = mock_post.call_args
            assert "/api/generate" in call_kwargs[0][0]
            assert call_kwargs[1]["json"]["model"] == "llama3.2"
            assert call_kwargs[1]["json"]["stream"] is False

    def test_fallback_http_timeout(self, client):
        with patch("cannalchemy.explain.llm.httpx.post", side_effect=httpx.TimeoutException("timeout")):
            result = client._call_fallback("test")
            assert result is None

    def test_empty_response_rejected(self, client):
        """Empty or too-long responses return None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"content": [{"type": "text", "text": ""}]}
        with patch("cannalchemy.explain.llm.httpx.post", return_value=mock_response):
            assert client._call_primary("test") is None


from cannalchemy.explain.cache import ExplanationCache
from cannalchemy.data.schema import init_db


class TestExplanationCache:
    @pytest.fixture
    def cache(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        return ExplanationCache(db_path)

    def test_miss_returns_none(self, cache):
        result = cache.get(strain_id=1, explanation_type="full", model_version="v2")
        assert result is None

    def test_put_then_get(self, cache):
        cache.put(
            strain_id=1, explanation_type="full", model_version="v2",
            content="Myrcene drives relaxation.", llm_provider="zai",
        )
        result = cache.get(strain_id=1, explanation_type="full", model_version="v2")
        assert result["content"] == "Myrcene drives relaxation."
        assert result["llm_provider"] == "zai"
        assert result["cached"] is True

    def test_different_model_version_misses(self, cache):
        cache.put(
            strain_id=1, explanation_type="full", model_version="v1",
            content="Old explanation.", llm_provider="zai",
        )
        result = cache.get(strain_id=1, explanation_type="full", model_version="v2")
        assert result is None

    def test_summary_and_full_independent(self, cache):
        cache.put(strain_id=1, explanation_type="full", model_version="v2",
                  content="Full text.", llm_provider="zai")
        cache.put(strain_id=1, explanation_type="summary", model_version="v2",
                  content="Short.", llm_provider="ollama")
        full = cache.get(strain_id=1, explanation_type="full", model_version="v2")
        summary = cache.get(strain_id=1, explanation_type="summary", model_version="v2")
        assert full["content"] == "Full text."
        assert summary["content"] == "Short."
        assert summary["llm_provider"] == "ollama"
