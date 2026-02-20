# Phase 5: LLM Explanations — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a pluggable LLM explanation layer (Z.AI primary, Ollama fallback) that generates human-readable prose explaining why predicted effects occur, displayed on strain detail pages and optionally on Explorer match cards.

**Architecture:** New `cannalchemy/explain/llm.py` module handles LLM calls with provider fallback. Explanations are generated on-demand and cached in a `strain_explanations` SQLite table keyed by `(strain_id, type, model_version)`. The frontend fetches explanations asynchronously — graceful degradation if LLM is unavailable.

**Tech Stack:** Python (httpx for HTTP), SQLite (cache), FastAPI (endpoints), React (UI components)

---

### Task 1: LLM Client — Core Module

**Files:**
- Create: `cannalchemy/explain/__init__.py` (already exists, empty)
- Create: `cannalchemy/explain/llm.py`
- Create: `tests/test_explain.py`

**Step 1: Write failing tests for LLMClient**

Create `tests/test_explain.py`:

```python
"""Tests for LLM explanation client."""
import json
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
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_explain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cannalchemy.explain.llm'`

**Step 3: Write minimal LLMClient implementation**

Create `cannalchemy/explain/llm.py`:

```python
"""Pluggable LLM client with provider fallback for strain explanations."""
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

# Prompt templates
FULL_EXPLANATION_PROMPT = """You are a cannabis scientist explaining strain effects to an informed consumer.
Given this strain's chemistry and predicted effects, explain WHY these effects
occur at the molecular level. Be specific about which terpenes/cannabinoids
drive which effects and mention receptor interactions when available.

Strain: {name} ({strain_type})
Terpenes: {terpenes}
Cannabinoids: {cannabinoids}
Top predicted effects: {effects}
Receptor pathways: {pathways}

Write 2-4 sentences. Use an accessible but scientific tone — like a well-informed
budtender with a biochemistry background."""

SUMMARY_PROMPT = """Summarize this strain's key effect in one sentence (max 20 words).
Strain: {name}, dominant terpene: {dominant_terpene}, top effect: {top_effect} ({top_prob}%)"""


class LLMClient:
    """Pluggable LLM client. Tries primary (Z.AI/Anthropic-compatible), falls back to Ollama."""

    def __init__(
        self,
        primary_url: str,
        primary_model: str,
        primary_key: str,
        fallback_url: str | None = None,
        fallback_model: str | None = None,
        primary_timeout: float = 10.0,
        fallback_timeout: float = 15.0,
    ):
        self.primary_url = primary_url
        self.primary_model = primary_model
        self.primary_key = primary_key
        self.fallback_url = fallback_url
        self.fallback_model = fallback_model
        self.primary_timeout = primary_timeout
        self.fallback_timeout = fallback_timeout
        self._rate_limited_until: float = 0  # timestamp when rate limit expires

    @classmethod
    def from_env(cls) -> "LLMClient | None":
        """Create from environment variables. Returns None if primary not configured."""
        primary_url = os.environ.get("CANNALCHEMY_LLM_PRIMARY_URL")
        primary_key = os.environ.get("CANNALCHEMY_LLM_PRIMARY_KEY")
        if not primary_url or not primary_key:
            return None
        return cls(
            primary_url=primary_url,
            primary_model=os.environ.get("CANNALCHEMY_LLM_PRIMARY_MODEL", "glm-4.7"),
            primary_key=primary_key,
            fallback_url=os.environ.get("CANNALCHEMY_LLM_FALLBACK_URL"),
            fallback_model=os.environ.get("CANNALCHEMY_LLM_FALLBACK_MODEL", "llama3.2"),
        )

    def _format_strain_data(self, strain_data: dict) -> dict:
        """Extract formatted strings from strain_data for prompt interpolation."""
        compositions = strain_data.get("compositions", [])
        terpenes = [c for c in compositions if c.get("type") == "terpene"]
        cannabinoids = [c for c in compositions if c.get("type") == "cannabinoid"]
        effects = strain_data.get("predicted_effects", [])
        pathways = strain_data.get("pathways", [])

        return {
            "name": strain_data.get("name", "Unknown"),
            "strain_type": strain_data.get("strain_type", "hybrid"),
            "terpenes": ", ".join(
                f"{t['molecule']} ({t['percentage']:.2f}%)" for t in terpenes[:5]
            ) or "none reported",
            "cannabinoids": ", ".join(
                f"{c['molecule'].upper()} ({c['percentage']:.1f}%)" for c in cannabinoids
            ) or "none reported",
            "effects": ", ".join(
                f"{e['name']} ({e['probability']:.0%}, {e.get('confidence', 'medium')} confidence)"
                for e in effects[:5]
            ) or "none predicted",
            "pathways": ", ".join(
                f"{p['molecule']} → {p['receptor']}" + (f" (Ki={p['ki_nm']:.0f}nM)" if p.get("ki_nm") else "")
                for p in pathways[:5]
            ) or "no pathway data",
            "dominant_terpene": terpenes[0]["molecule"] if terpenes else "unknown",
            "top_effect": effects[0]["name"] if effects else "unknown",
            "top_prob": f"{effects[0]['probability'] * 100:.0f}" if effects else "0",
        }

    def _call_primary(self, prompt: str) -> str | None:
        """Call primary provider (Anthropic-compatible API)."""
        if time.time() < self._rate_limited_until:
            logger.debug("Primary rate-limited, skipping")
            return None
        try:
            resp = httpx.post(
                self.primary_url,
                headers={
                    "x-api-key": self.primary_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.primary_model,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.primary_timeout,
            )
            if resp.status_code == 429:
                self._rate_limited_until = time.time() + 60
                logger.warning("Primary rate-limited for 60s")
                return None
            resp.raise_for_status()
            data = resp.json()
            text = data.get("content", [{}])[0].get("text", "").strip()
            return text if text and len(text) < 2000 else None
        except (httpx.TimeoutException, httpx.HTTPStatusError, Exception) as e:
            logger.warning("Primary LLM failed: %s", e)
            return None

    def _call_fallback(self, prompt: str) -> str | None:
        """Call fallback provider (Ollama API)."""
        if not self.fallback_url:
            return None
        try:
            resp = httpx.post(
                f"{self.fallback_url}/api/generate",
                json={
                    "model": self.fallback_model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=self.fallback_timeout,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            return text if text and len(text) < 2000 else None
        except (httpx.TimeoutException, httpx.HTTPStatusError, Exception) as e:
            logger.warning("Fallback LLM failed: %s", e)
            return None

    def _generate(self, prompt: str) -> tuple[str | None, str | None]:
        """Try primary, then fallback. Returns (text, provider_name)."""
        text = self._call_primary(prompt)
        if text:
            return text, "zai"
        text = self._call_fallback(prompt)
        if text:
            return text, "ollama"
        return None, None

    def explain_strain(self, strain_data: dict) -> tuple[str | None, str | None]:
        """Generate 2-4 sentence explanation. Returns (text, provider)."""
        fmt = self._format_strain_data(strain_data)
        prompt = FULL_EXPLANATION_PROMPT.format(**fmt)
        return self._generate(prompt)

    def summarize_strain(self, strain_data: dict) -> tuple[str | None, str | None]:
        """Generate 1-line summary. Returns (text, provider)."""
        fmt = self._format_strain_data(strain_data)
        prompt = SUMMARY_PROMPT.format(**fmt)
        return self._generate(prompt)
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_explain.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add cannalchemy/explain/llm.py tests/test_explain.py
git commit -m "feat: add pluggable LLM client with provider fallback"
```

---

### Task 2: LLM Client — Provider Call Tests

**Files:**
- Modify: `tests/test_explain.py`

**Step 1: Add tests for primary/fallback call logic**

Append to `tests/test_explain.py`:

```python
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
```

Add `import time` at top of the test file.

**Step 2: Run tests**

Run: `.venv/bin/pytest tests/test_explain.py -v`
Expected: All 10 tests PASS (4 init + 6 call tests)

**Step 3: Commit**

```bash
git add tests/test_explain.py
git commit -m "test: add LLM client provider fallback tests"
```

---

### Task 3: LLM Client — HTTP Integration Tests

**Files:**
- Modify: `tests/test_explain.py`

**Step 1: Add HTTP-level tests using httpx mocking**

Append to `tests/test_explain.py`:

```python
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
```

**Step 2: Run tests**

Run: `.venv/bin/pytest tests/test_explain.py -v`
Expected: All 16 tests PASS

**Step 3: Commit**

```bash
git add tests/test_explain.py
git commit -m "test: add LLM client HTTP integration tests"
```

---

### Task 4: Cache Table + Cache Logic

**Files:**
- Modify: `cannalchemy/data/schema.py` — add `strain_explanations` table to schema
- Create: `cannalchemy/explain/cache.py` — cache read/write helpers
- Modify: `tests/test_explain.py` — add cache tests

**Step 1: Write failing cache tests**

Append to `tests/test_explain.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_explain.py::TestExplanationCache -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cannalchemy.explain.cache'`

**Step 3: Add table to schema**

In `cannalchemy/data/schema.py`, add to the end of `SCHEMA_SQL` (before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS strain_explanations (
    strain_id INTEGER NOT NULL,
    explanation_type TEXT NOT NULL,
    content TEXT NOT NULL,
    model_version TEXT NOT NULL,
    llm_provider TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (strain_id, explanation_type, model_version)
);
```

Also add `"strain_explanations"` to the `DB_TABLES` list.

**Step 4: Write cache module**

Create `cannalchemy/explain/cache.py`:

```python
"""SQLite cache for LLM-generated strain explanations."""
import sqlite3


class ExplanationCache:
    """Read/write cache for strain explanations, keyed by (strain_id, type, model_version)."""

    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Ensure table exists (idempotent)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS strain_explanations (
                strain_id INTEGER NOT NULL,
                explanation_type TEXT NOT NULL,
                content TEXT NOT NULL,
                model_version TEXT NOT NULL,
                llm_provider TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (strain_id, explanation_type, model_version)
            )
        """)
        self._conn.commit()

    def get(self, strain_id: int, explanation_type: str, model_version: str) -> dict | None:
        row = self._conn.execute(
            "SELECT content, llm_provider, created_at FROM strain_explanations "
            "WHERE strain_id = ? AND explanation_type = ? AND model_version = ?",
            (strain_id, explanation_type, model_version),
        ).fetchone()
        if not row:
            return None
        return {
            "content": row["content"],
            "llm_provider": row["llm_provider"],
            "created_at": row["created_at"],
            "cached": True,
        }

    def put(
        self,
        strain_id: int,
        explanation_type: str,
        model_version: str,
        content: str,
        llm_provider: str,
    ) -> None:
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO strain_explanations "
                "(strain_id, explanation_type, content, model_version, llm_provider) "
                "VALUES (?, ?, ?, ?, ?)",
                (strain_id, explanation_type, content, model_version, llm_provider),
            )
            self._conn.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Cache write failed: %s", e)
```

**Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_explain.py::TestExplanationCache -v`
Expected: All 4 cache tests PASS

**Step 6: Run full test suite to check no regressions**

Run: `.venv/bin/pytest tests/test_explain.py -v`
Expected: All 20 tests PASS

**Step 7: Commit**

```bash
git add cannalchemy/data/schema.py cannalchemy/explain/cache.py tests/test_explain.py
git commit -m "feat: add explanation cache with SQLite backing"
```

---

### Task 5: API Endpoint — `/strains/{name}/explain`

**Files:**
- Modify: `cannalchemy/api/app.py` — add explain endpoint + LLM client initialization
- Create: `tests/test_api_explain.py`

**Step 1: Write failing integration test**

Create `tests/test_api_explain.py`:

```python
"""Tests for the /strains/{name}/explain endpoint."""
import threading
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import CANONICAL_EFFECTS
from cannalchemy.models.effect_predictor import EffectPredictor


@pytest.fixture
def populated_db(tmp_path):
    """Create a test DB with strains + compositions."""
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('limonene', 'terpene')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('thc', 'cannabinoid')")
    conn.execute(
        "INSERT INTO receptors (name, gene_name, function) VALUES ('CB1', 'CNR1', 'pain modulation')"
    )
    conn.execute(
        "INSERT INTO binding_affinities (molecule_id, receptor_id, ki_nm, action_type, source) "
        "VALUES (1, 1, 50.0, 'agonist', 'test')"
    )
    for ce in CANONICAL_EFFECTS:
        conn.execute(
            "INSERT OR IGNORE INTO effects (name, category) VALUES (?, ?)",
            (ce["name"], ce["category"]),
        )
    conn.execute(
        "INSERT INTO strains (name, normalized_name, strain_type, source) "
        "VALUES ('Blue Dream', 'bluedream', 'hybrid', 'test')"
    )
    conn.execute(
        "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) "
        "VALUES (1, 1, 0.35, 'test')"
    )
    conn.execute(
        "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) "
        "VALUES (1, 2, 0.28, 'test')"
    )
    conn.execute(
        "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) "
        "VALUES (1, 3, 21.0, 'test')"
    )
    conn.execute(
        "INSERT INTO effect_reports (strain_id, effect_id, report_count, source) "
        "VALUES (1, 1, 15, 'test')"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def trained_predictor(tmp_path):
    rng = np.random.RandomState(42)
    n = 50
    X = pd.DataFrame(
        {"myrcene": rng.uniform(0, 1, n), "limonene": rng.uniform(0, 1, n),
         "thc": rng.uniform(10, 30, n)},
        index=range(1, n + 1),
    )
    X.index.name = "strain_id"
    y = pd.DataFrame(index=X.index)
    y.index.name = "strain_id"
    y["relaxed"] = (X["myrcene"] > 0.5).astype(int)
    y["energetic"] = (X["limonene"] > 0.5).astype(int)
    predictor = EffectPredictor(calibrate=False)
    predictor.train(X, y, n_folds=3)
    save_path = str(tmp_path / "model")
    predictor.save(save_path)
    return save_path


@pytest.fixture
def client(populated_db, trained_predictor, monkeypatch):
    import cannalchemy.api.app as api_module
    monkeypatch.setattr(api_module, "DEFAULT_MODEL_DIR", trained_predictor)
    monkeypatch.setattr(api_module, "FALLBACK_MODEL_DIR", trained_predictor)
    monkeypatch.setattr(api_module, "_predictor", None)
    monkeypatch.setattr(api_module, "DB_PATH", populated_db)
    monkeypatch.setattr(api_module, "_db_conn", None)
    monkeypatch.setattr(api_module, "_knowledge_graph", None)
    monkeypatch.setattr(api_module, "_prediction_cache", None)
    monkeypatch.setattr(api_module, "_cache_ready", threading.Event())
    monkeypatch.setattr(api_module, "_explanation_cache", None)
    # Mock the LLM client
    mock_llm = MagicMock()
    mock_llm.explain_strain.return_value = ("Myrcene drives relaxation via CB1.", "zai")
    mock_llm.summarize_strain.return_value = ("Relaxing hybrid.", "zai")
    monkeypatch.setattr(api_module, "_llm_client", mock_llm)
    return TestClient(api_module.app)


class TestExplainEndpoint:
    def test_explain_returns_explanation(self, client):
        resp = client.get("/strains/Blue%20Dream/explain")
        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] == "Myrcene drives relaxation via CB1."
        assert data["provider"] == "zai"

    def test_explain_nonexistent_strain(self, client):
        resp = client.get("/strains/Nonexistent/explain")
        assert resp.status_code == 404

    def test_explain_caches_result(self, client):
        # First call generates
        resp1 = client.get("/strains/Blue%20Dream/explain")
        assert resp1.json()["cached"] is False
        # Second call should be cached
        resp2 = client.get("/strains/Blue%20Dream/explain")
        assert resp2.json()["cached"] is True
        assert resp2.json()["explanation"] == resp1.json()["explanation"]

    def test_explain_llm_unavailable(self, client, monkeypatch):
        import cannalchemy.api.app as api_module
        mock_llm = MagicMock()
        mock_llm.explain_strain.return_value = (None, None)
        monkeypatch.setattr(api_module, "_llm_client", mock_llm)
        resp = client.get("/strains/Blue%20Dream/explain")
        assert resp.status_code == 200
        assert resp.json()["explanation"] is None

    def test_explain_no_llm_configured(self, client, monkeypatch):
        import cannalchemy.api.app as api_module
        monkeypatch.setattr(api_module, "_llm_client", None)
        resp = client.get("/strains/Blue%20Dream/explain")
        assert resp.status_code == 200
        assert resp.json()["explanation"] is None
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_api_explain.py -v`
Expected: FAIL — endpoint doesn't exist yet

**Step 3: Add explain endpoint to app.py**

Add these globals near the top of `app.py` (after line 59, with the other globals):

```python
from cannalchemy.explain.llm import LLMClient
from cannalchemy.explain.cache import ExplanationCache

_llm_client: LLMClient | None = None
_explanation_cache: ExplanationCache | None = None
```

Add initialization in `_warmup_all()` (after graph build, before prediction cache):

```python
    # Initialize LLM client + cache
    global _llm_client, _explanation_cache
    _llm_client = LLMClient.from_env()
    if _llm_client:
        print("Warmup: LLM client configured (primary + fallback)")
    else:
        print("Warmup: LLM not configured (no CANNALCHEMY_LLM_PRIMARY_URL)")
    _explanation_cache = ExplanationCache(DB_PATH)
```

Add helper to get model version:

```python
def _get_model_version() -> str:
    """Get current model version string for cache keying."""
    return Path(DEFAULT_MODEL_DIR).name if Path(DEFAULT_MODEL_DIR).exists() else Path(FALLBACK_MODEL_DIR).name
```

Add the endpoint (after the `get_strain` endpoint, around line 539):

```python
@app.get("/strains/{name}/explain")
def explain_strain(name: str):
    """Get LLM-generated explanation for a strain's predicted effects."""
    conn = _get_db()
    row = conn.execute(
        "SELECT id, name, strain_type FROM strains WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Strain '{name}' not found")

    if not _llm_client:
        return {"explanation": None, "provider": None, "cached": False}

    strain_id = row["id"]
    model_version = _get_model_version()

    # Check cache
    if _explanation_cache:
        cached = _explanation_cache.get(strain_id, "full", model_version)
        if cached:
            return {
                "explanation": cached["content"],
                "provider": cached["llm_provider"],
                "cached": True,
            }

    # Build strain data for prompt
    comps = conn.execute(
        "SELECT m.name as molecule, sc.percentage, m.molecule_type as type "
        "FROM strain_compositions sc JOIN molecules m ON sc.molecule_id = m.id "
        "WHERE sc.strain_id = ? ORDER BY sc.percentage DESC",
        (strain_id,),
    ).fetchall()
    compositions = [{"molecule": c["molecule"], "percentage": c["percentage"], "type": c["type"]} for c in comps]

    predicted_effects = []
    try:
        predictor = _get_predictor()
        predicted_effects = _predict_for_composition(compositions, row["strain_type"], predictor)
    except Exception:
        pass

    G = _get_graph()
    pathways = []
    for comp in compositions:
        pathways.extend(get_molecule_pathways(G, comp["molecule"]))

    strain_data = {
        "name": row["name"],
        "strain_type": row["strain_type"],
        "compositions": compositions,
        "predicted_effects": predicted_effects[:5],
        "pathways": [
            {"molecule": p["molecule"], "receptor": p["receptor"], "ki_nm": p.get("ki_nm")}
            for p in pathways[:5]
        ],
    }

    text, provider = _llm_client.explain_strain(strain_data)
    if text and _explanation_cache:
        _explanation_cache.put(strain_id, "full", model_version, text, provider)

    return {"explanation": text, "provider": provider, "cached": False}
```

Update the docstring at top of file to include the new endpoint.

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_api_explain.py -v`
Expected: All 5 tests PASS

**Step 5: Run existing tests for regression**

Run: `.venv/bin/pytest tests/ -v`
Expected: All tests PASS (existing + new)

**Step 6: Commit**

```bash
git add cannalchemy/api/app.py tests/test_api_explain.py
git commit -m "feat: add /strains/{name}/explain endpoint with caching"
```

---

### Task 6: Match Endpoint — Add `explain` Option

**Files:**
- Modify: `cannalchemy/api/app.py` — add `explain` field to `MatchRequest`, generate summaries
- Modify: `tests/test_api_explain.py` — add match+explain tests

**Step 1: Write failing test**

Append to `tests/test_api_explain.py`:

```python
class TestMatchExplain:
    def test_match_without_explain(self, client):
        resp = client.post("/match", json={"effects": ["relaxed"]})
        data = resp.json()
        # No summary field when explain not requested
        for strain in data["strains"]:
            assert "summary" not in strain

    def test_match_with_explain(self, client):
        resp = client.post("/match", json={"effects": ["relaxed"], "explain": True})
        data = resp.json()
        for strain in data["strains"]:
            assert "summary" in strain
            assert strain["summary"] == "Relaxing hybrid."
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_api_explain.py::TestMatchExplain -v`
Expected: FAIL — `explain` field not recognized / `summary` not in response

**Step 3: Implement**

Add `explain` to `MatchRequest` in `app.py`:

```python
class MatchRequest(BaseModel):
    """Request body for effect matching."""
    effects: list[str]
    type: str = "any"
    limit: int = 50
    explain: bool = False
```

In the `match_strains` function, after building `results` and before the return, add summary generation:

```python
    # Generate summaries if requested
    if request.explain and _llm_client:
        model_version = _get_model_version()
        for result in results:
            # Look up strain_id from name
            strain_row = conn.execute(
                "SELECT id FROM strains WHERE name = ?", (result["name"],)
            ).fetchone()
            if not strain_row:
                continue
            sid = strain_row["id"]

            # Check cache first
            if _explanation_cache:
                cached = _explanation_cache.get(sid, "summary", model_version)
                if cached:
                    result["summary"] = cached["content"]
                    continue

            # Generate summary
            strain_data = {
                "name": result["name"],
                "strain_type": result["strain_type"],
                "compositions": result["compositions"],
                "predicted_effects": result["top_effects"][:3],
                "pathways": [],
            }
            text, provider = _llm_client.summarize_strain(strain_data)
            if text:
                result["summary"] = text
                if _explanation_cache:
                    _explanation_cache.put(sid, "summary", model_version, text, provider)
```

Note: need to get a `conn` reference at the top of `match_strains`:

```python
    conn = _get_db()
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_api_explain.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add cannalchemy/api/app.py tests/test_api_explain.py
git commit -m "feat: add explain option to match endpoint for 1-line summaries"
```

---

### Task 7: Frontend — API Client + StrainDetail Explanation

**Files:**
- Modify: `frontend/src/lib/api.js` — add `fetchExplanation()`
- Modify: `frontend/src/pages/StrainDetail.jsx` — add AI Analysis section

**Step 1: Add API function**

Add to `frontend/src/lib/api.js`:

```javascript
export function fetchExplanation(name) {
  return request(`/strains/${encodeURIComponent(name)}/explain`);
}
```

**Step 2: Update StrainDetail.jsx**

Add explanation state and fetch:

```javascript
const [explanation, setExplanation] = useState(null);
const [explanationLoading, setExplanationLoading] = useState(false);
```

In the `useEffect` that fetches strain data, after `setStrain(data)`:

```javascript
// Fetch explanation async (non-blocking)
setExplanationLoading(true);
fetchExplanation(name)
  .then((data) => setExplanation(data))
  .catch(() => setExplanation(null))
  .finally(() => setExplanationLoading(false));
```

Add import of `fetchExplanation` at top.

Add the AI Analysis card after the pathway diagram section (before "Similar strains"):

```jsx
{/* AI Analysis */}
{(explanationLoading || (explanation && explanation.explanation)) && (
  <div className="card animate-fade-in-up" style={{ padding: 24, marginBottom: 32 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
      <h2
        className="font-display"
        style={{ fontSize: "1.1rem", color: "var(--cream)", margin: 0 }}
      >
        AI Analysis
      </h2>
      {explanation?.provider && (
        <span
          className="font-data"
          style={{
            fontSize: "10px",
            color: "var(--cream-faint)",
            border: "1px solid var(--border)",
            borderRadius: 4,
            padding: "2px 6px",
          }}
        >
          {explanation.provider.toUpperCase()}
        </span>
      )}
    </div>
    {explanationLoading ? (
      <div className="skeleton" style={{ height: 60, borderRadius: 4 }} />
    ) : (
      <p style={{ color: "var(--cream-dim)", fontSize: "14px", lineHeight: 1.7, margin: 0 }}>
        {explanation.explanation}
      </p>
    )}
  </div>
)}
```

**Step 3: Verify locally (manual)**

Run: `cd frontend && npm run dev` — open a strain detail page, confirm:
- Explanation section appears below pathway diagram
- Shows shimmer while loading
- Shows text with provider badge when loaded
- Hidden entirely if LLM not configured (explanation is null)

**Step 4: Commit**

```bash
git add frontend/src/lib/api.js frontend/src/pages/StrainDetail.jsx
git commit -m "feat: add AI Analysis section to strain detail page"
```

---

### Task 8: Frontend — Explorer Summaries + Toggle

**Files:**
- Modify: `frontend/src/lib/api.js` — update `matchEffects()` to accept explain param
- Modify: `frontend/src/pages/Explorer.jsx` — add toggle
- Modify: `frontend/src/components/StrainCard.jsx` — show summary line

**Step 1: Update API client**

In `frontend/src/lib/api.js`, modify `matchEffects`:

```javascript
export function matchEffects(effects, type = "", limit = 20, explain = false) {
  return request("/match", {
    method: "POST",
    body: JSON.stringify({ effects, type: type || undefined, limit, explain }),
  });
}
```

**Step 2: Add toggle to Explorer.jsx**

Add state:

```javascript
const [showSummaries, setShowSummaries] = useState(false);
```

Update the `matchEffects` call in the `search` callback:

```javascript
const data = await matchEffects(selectedEffects, typeFilter, 24, showSummaries);
```

Add `showSummaries` to the dependency array of the `useCallback`.

Add toggle button in the filters row (after type filter pills, before selection summary):

```jsx
{selectedEffects.length > 0 && (
  <button
    type="button"
    onClick={() => setShowSummaries(!showSummaries)}
    style={{
      padding: "6px 12px",
      borderRadius: "20px",
      border: `1px solid ${showSummaries ? "var(--gold-dim)" : "var(--border)"}`,
      background: showSummaries ? "rgba(212,168,67,0.08)" : "transparent",
      color: showSummaries ? "var(--gold)" : "var(--cream-faint)",
      fontSize: "12px",
      fontFamily: "var(--font-body)",
      cursor: "pointer",
      transition: "all 150ms",
    }}
  >
    {showSummaries ? "✦ " : ""}AI Summaries
  </button>
)}
```

**Step 3: Add summary line to StrainCard.jsx**

After the header row div (after the `{score != null && ...}` block), add:

```jsx
{/* AI summary line */}
{strain.summary && (
  <p
    style={{
      margin: 0,
      fontSize: "12px",
      fontStyle: "italic",
      color: "var(--cream-faint)",
      lineHeight: 1.4,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
    }}
  >
    {strain.summary}
  </p>
)}
```

**Step 4: Commit**

```bash
git add frontend/src/lib/api.js frontend/src/pages/Explorer.jsx frontend/src/components/StrainCard.jsx
git commit -m "feat: add AI summaries toggle to Explorer with 1-line strain summaries"
```

---

### Task 9: Docker Configuration

**Files:**
- Modify: `docker-compose.yml` — add env vars + extra_hosts
- Create: `cannalchemy.env` — env file with LLM config

**Step 1: Create env file**

Create `cannalchemy.env` in the project root (gitignored):

```
CANNALCHEMY_LLM_PRIMARY_URL=https://api.z.ai/api/anthropic/v1/messages
CANNALCHEMY_LLM_PRIMARY_MODEL=glm-4.7
CANNALCHEMY_LLM_PRIMARY_KEY=<copy from ~/config/n8n.env ZAI_API_KEY>
CANNALCHEMY_LLM_FALLBACK_URL=http://host.docker.internal:11434
CANNALCHEMY_LLM_FALLBACK_MODEL=llama3.2
```

**Step 2: Update docker-compose.yml**

```yaml
services:
  cannalchemy:
    build: .
    container_name: cannalchemy
    restart: unless-stopped
    ports:
      - "8422:8080"
    env_file:
      - cannalchemy.env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - /srv/appdata/cannalchemy/cannalchemy.db:/app/data/processed/cannalchemy.db:ro
      - /srv/appdata/cannalchemy/models.pkl:/app/data/models/v2/models.pkl:ro
      - /srv/appdata/cannalchemy/metadata.json:/app/data/models/v2/metadata.json:ro
```

Note: The DB is mounted read-only. The explanation cache table needs a writable DB. Change the volume mount to remove `:ro` OR mount a separate writable copy for the cache. **Recommendation:** Mount as read-write (remove `:ro`) since explanations need to be written.

**Step 3: Add env file to .gitignore**

Append to `.gitignore`:

```
cannalchemy.env
```

**Step 4: Commit**

```bash
git add docker-compose.yml .gitignore
git commit -m "feat: add LLM env config and Ollama access to Docker compose"
```

---

### Task 10: E2E Test

**Files:**
- Create: `frontend/e2e/explain.spec.js`

**Step 1: Write E2E test**

Create `frontend/e2e/explain.spec.js`:

```javascript
import { test, expect } from "@playwright/test";

test.describe("Strain Explanation", () => {
  test("explain endpoint returns response", async ({ request }) => {
    // Get a strain name first
    const listRes = await request.get("http://localhost:8421/strains?limit=1");
    const listData = await listRes.json();
    const name = listData.strains[0].name;

    const res = await request.get(
      `http://localhost:8421/strains/${encodeURIComponent(name)}/explain`
    );
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    // Explanation may be null if LLM not configured — just verify structure
    expect(data).toHaveProperty("explanation");
    expect(data).toHaveProperty("provider");
    expect(data).toHaveProperty("cached");
  });

  test("strain detail page loads without explanation errors", async ({ page }) => {
    // Get a strain name via API
    const listRes = await page.request.get("http://localhost:8421/strains?limit=1");
    const listData = await listRes.json();
    const name = listData.strains[0].name;

    await page.goto(`/strain/${encodeURIComponent(name)}`);
    // Page should load successfully (explanation may or may not appear depending on LLM config)
    await expect(page.getByText(name)).toBeVisible({ timeout: 10000 });
    // No error state
    await expect(page.getByText("Strain Not Found")).not.toBeVisible();
  });
});
```

**Step 2: Run E2E tests (requires running Docker container)**

Run: `cd frontend && npx playwright test e2e/explain.spec.js`
Expected: Both tests PASS

**Step 3: Commit**

```bash
git add frontend/e2e/explain.spec.js
git commit -m "test: add E2E tests for strain explanation endpoint and page"
```

---

### Task 11: Build, Deploy, Verify

**Files:** No new files — build and deployment verification

**Step 1: Run full pytest suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: All tests PASS (existing 22 + ~15 new explain tests)

**Step 2: Build Docker image**

Run: `docker compose build`
Expected: Build succeeds

**Step 3: Create env file with real credentials**

```bash
grep ZAI_API_KEY ~/config/n8n.env | sed 's/ZAI_API_KEY/CANNALCHEMY_LLM_PRIMARY_KEY/' > cannalchemy.env
echo 'CANNALCHEMY_LLM_PRIMARY_URL=https://api.z.ai/api/anthropic/v1/messages' >> cannalchemy.env
echo 'CANNALCHEMY_LLM_PRIMARY_MODEL=glm-4.7' >> cannalchemy.env
echo 'CANNALCHEMY_LLM_FALLBACK_URL=http://host.docker.internal:11434' >> cannalchemy.env
echo 'CANNALCHEMY_LLM_FALLBACK_MODEL=llama3.2' >> cannalchemy.env
```

**Step 4: Deploy**

Run: `docker compose up -d`

**Step 5: Verify health**

Run: `curl -s http://localhost:8422/api/health | python3 -m json.tool`
Expected: `{"status": "healthy", ...}`

**Step 6: Verify explanation endpoint**

Run: `curl -s 'http://localhost:8422/api/strains/Blue%20Dream/explain' | python3 -m json.tool`
Expected: JSON with `explanation` (non-null if LLM is reachable), `provider`, `cached`

**Step 7: Verify explanation caching**

Run the same curl again — `cached` should be `true`

**Step 8: Run Playwright E2E suite**

Run: `cd frontend && npx playwright test`
Expected: All tests PASS (24 existing + 2 new)

**Step 9: Commit any deployment fixes**

If anything needed fixing during deploy, commit the fixes.

---

### Task 12: Documentation Update

**Files:**
- Modify: `CLAUDE.md` — update Phase 5 status
- Modify: `docs/SESSION-LOG.md` — add Phase 5 section

**Step 1: Update CLAUDE.md**

Change Phase 5 status from `NOT STARTED` to `COMPLETE` in the phase table.

Add new endpoint to API endpoints table:
```
| `/strains/{name}/explain` | GET | LLM explanation for strain (cached) |
```

Add to Architecture section:
```
- **LLM Explanation**: Z.AI (glm-4.7) primary, Ollama (llama3.2) fallback, SQLite cache
```

**Step 2: Update SESSION-LOG.md**

Add Phase 5 section documenting what was built.

**Step 3: Commit**

```bash
git add CLAUDE.md docs/SESSION-LOG.md
git commit -m "docs: mark Phase 5 LLM Explanations as complete"
```

**Step 4: Push**

```bash
git push
```
