"""Tests for strain-related API endpoints (Phase 3)."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import CANONICAL_EFFECTS
from cannalchemy.models.effect_predictor import EffectPredictor


@pytest.fixture
def populated_db(tmp_path):
    """Create a test DB with strains, compositions, effects, and graph data."""
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)

    # Seed molecules
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('limonene', 'terpene')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('thc', 'cannabinoid')")

    # Seed receptors
    conn.execute(
        "INSERT INTO receptors (name, gene_name, function) VALUES ('CB1', 'CNR1', 'pain modulation')"
    )

    # Seed binding affinities
    conn.execute(
        "INSERT INTO binding_affinities (molecule_id, receptor_id, ki_nm, action_type, source) "
        "VALUES (1, 1, 50.0, 'agonist', 'test')"
    )

    # Seed effects
    for ce in CANONICAL_EFFECTS:
        conn.execute(
            "INSERT OR IGNORE INTO effects (name, category) VALUES (?, ?)",
            (ce["name"], ce["category"]),
        )

    # Seed strains with compositions
    for i, (name, stype) in enumerate(
        [("Blue Dream", "hybrid"), ("OG Kush", "indica"), ("Sour Diesel", "sativa")],
        1,
    ):
        conn.execute(
            "INSERT INTO strains (name, normalized_name, strain_type, source) "
            "VALUES (?, ?, ?, 'test')",
            (name, name.lower().replace(" ", ""), stype),
        )
        conn.execute(
            "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) "
            "VALUES (?, 1, ?, 'test')",
            (i, 0.3 + i * 0.1),
        )
        conn.execute(
            "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) "
            "VALUES (?, 2, ?, 'test')",
            (i, 0.2 + i * 0.05),
        )
        conn.execute(
            "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) "
            "VALUES (?, 3, ?, 'test')",
            (i, 15.0 + i * 2),
        )
        # Seed effect reports
        conn.execute(
            "INSERT INTO effect_reports (strain_id, effect_id, report_count, source) "
            "VALUES (?, 1, ?, 'test')",
            (i, 10 + i * 5),
        )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def trained_predictor(tmp_path):
    """Create a minimal trained predictor."""
    rng = np.random.RandomState(42)
    n = 50
    X = pd.DataFrame(
        {
            "myrcene": rng.uniform(0, 1, n),
            "limonene": rng.uniform(0, 1, n),
            "thc": rng.uniform(10, 30, n),
        },
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
    """Create test client with populated DB and model."""
    import cannalchemy.api.app as api_module

    monkeypatch.setattr(api_module, "DEFAULT_MODEL_DIR", trained_predictor)
    monkeypatch.setattr(api_module, "FALLBACK_MODEL_DIR", trained_predictor)
    monkeypatch.setattr(api_module, "_predictor", None)
    monkeypatch.setattr(api_module, "DB_PATH", populated_db)
    monkeypatch.setattr(api_module, "_db_conn", None)
    monkeypatch.setattr(api_module, "_knowledge_graph", None)
    return TestClient(api_module.app)


class TestStrainsEndpoint:
    def test_list_strains(self, client):
        resp = client.get("/strains")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["strains"]) == 3

    def test_search_strains(self, client):
        resp = client.get("/strains?q=blue")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["strains"]) == 1
        assert data["strains"][0]["name"] == "Blue Dream"

    def test_filter_by_type(self, client):
        resp = client.get("/strains?type=indica")
        data = resp.json()
        assert all(s["strain_type"] == "indica" for s in data["strains"])

    def test_strain_has_compositions(self, client):
        resp = client.get("/strains")
        strain = resp.json()["strains"][0]
        assert "compositions" in strain
        assert len(strain["compositions"]) > 0

    def test_limit_results(self, client):
        resp = client.get("/strains?limit=1")
        data = resp.json()
        assert len(data["strains"]) == 1


class TestStrainDetailEndpoint:
    def test_get_strain(self, client):
        resp = client.get("/strains/Blue Dream")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Blue Dream"
        assert "compositions" in data
        assert "predicted_effects" in data
        assert "pathways" in data

    def test_strain_not_found(self, client):
        resp = client.get("/strains/Nonexistent")
        assert resp.status_code == 404


class TestMatchEndpoint:
    def test_match_effects(self, client):
        resp = client.post("/match", json={"effects": ["relaxed"]})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["strains"]) > 0
        assert "score" in data["strains"][0]

    def test_match_with_type_filter(self, client):
        resp = client.post(
            "/match", json={"effects": ["relaxed"], "type": "indica"}
        )
        data = resp.json()
        assert all(s["strain_type"] == "indica" for s in data["strains"])

    def test_match_sorted_by_score(self, client):
        resp = client.post("/match", json={"effects": ["relaxed"]})
        data = resp.json()
        scores = [s["score"] for s in data["strains"]]
        assert scores == sorted(scores, reverse=True)


class TestGraphEndpoint:
    def test_get_graph(self, client):
        resp = client.get("/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0

    def test_graph_node_has_type(self, client):
        resp = client.get("/graph")
        data = resp.json()
        for node in data["nodes"]:
            assert "type" in node
            assert node["type"] in ("molecule", "receptor", "effect")

    def test_graph_node_detail(self, client):
        resp = client.get("/graph/molecule:myrcene")
        assert resp.status_code == 200
        data = resp.json()
        assert data["node"]["name"] == "myrcene"
        assert "connected" in data


class TestStatsEndpoint:
    def test_get_stats(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_strains" in data
        assert "ml_ready_strains" in data
        assert "molecules" in data
        assert "effects" in data
        assert data["total_strains"] == 3
