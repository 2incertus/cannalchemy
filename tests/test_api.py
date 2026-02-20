"""Tests for the prediction API."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cannalchemy.models.effect_predictor import EffectPredictor


@pytest.fixture
def trained_predictor(tmp_path):
    """Create and save a minimal trained predictor."""
    rng = np.random.RandomState(42)
    n = 50

    X = pd.DataFrame({
        "myrcene": rng.uniform(0, 1, n),
        "limonene": rng.uniform(0, 1, n),
        "thc": rng.uniform(10, 30, n),
    }, index=range(1, n + 1))
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
def client(trained_predictor, monkeypatch):
    """Create a test client with the trained model."""
    import cannalchemy.api.app as api_module

    monkeypatch.setattr(api_module, "DEFAULT_MODEL_DIR", trained_predictor)
    monkeypatch.setattr(api_module, "FALLBACK_MODEL_DIR", trained_predictor)
    # Reset cached predictor
    monkeypatch.setattr(api_module, "_predictor", None)

    return TestClient(api_module.app)


class TestPredict:
    def test_basic_prediction(self, client):
        resp = client.post("/predict", json={"myrcene": 0.8, "thc": 25.0})
        assert resp.status_code == 200
        data = resp.json()
        assert "effects" in data
        assert isinstance(data["effects"], list)

    def test_all_defaults(self, client):
        resp = client.post("/predict", json={})
        assert resp.status_code == 200

    def test_threshold_filtering(self, client):
        resp = client.post(
            "/predict",
            json={"myrcene": 0.8, "thc": 25.0},
            params={"threshold": 0.9},
        )
        data = resp.json()
        for eff in data["effects"]:
            assert eff["probability"] >= 0.9

    def test_top_n(self, client):
        resp = client.post(
            "/predict",
            json={"myrcene": 0.8, "limonene": 0.8, "thc": 25.0},
            params={"threshold": 0.0, "top_n": 1},
        )
        data = resp.json()
        assert len(data["effects"]) <= 1

    def test_response_structure(self, client):
        resp = client.post(
            "/predict",
            json={"myrcene": 0.5},
            params={"threshold": 0.0},
        )
        data = resp.json()
        assert "model_version" in data
        assert "n_features_used" in data
        for eff in data["effects"]:
            assert "name" in eff
            assert "probability" in eff
            assert "predicted" in eff
            assert 0 <= eff["probability"] <= 1


class TestEndpoints:
    def test_effects_list(self, client):
        resp = client.get("/effects")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2  # relaxed, energetic

    def test_features_list(self, client):
        resp = client.get("/features")
        assert resp.status_code == 200
        assert resp.json()["count"] == 3  # myrcene, limonene, thc

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
