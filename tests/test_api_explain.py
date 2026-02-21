"""Tests for the /strains/{name}/explain endpoint."""
import threading
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import CANONICAL_EFFECTS
from cannalchemy.explain.cache import ExplanationCache
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
    monkeypatch.setattr(api_module, "_explanation_cache", ExplanationCache(populated_db))
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
