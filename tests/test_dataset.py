"""Tests for the ML dataset builder."""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import CANONICAL_EFFECTS, seed_canonical_effects
from cannalchemy.models.dataset import (
    build_dataset,
    build_feature_matrix,
    build_label_matrix,
    load_effects,
    load_ml_strain_ids,
    load_molecules,
)


@pytest.fixture
def ml_db(tmp_path):
    """Create a Cannalchemy DB with molecules, strains, compositions, and effects."""
    db_path = str(tmp_path / "cannalchemy.db")
    conn = init_db(db_path)
    seed_canonical_effects(conn)

    # Seed the effects table from canonical_effects (mimics what consumer_import does)
    for ce in CANONICAL_EFFECTS:
        conn.execute(
            "INSERT OR IGNORE INTO effects (name, category) VALUES (?, ?)",
            (ce["name"], ce["category"]),
        )

    # Insert molecules
    conn.execute(
        "INSERT INTO molecules (id, name, molecule_type) VALUES (1, 'myrcene', 'terpene')"
    )
    conn.execute(
        "INSERT INTO molecules (id, name, molecule_type) VALUES (2, 'limonene', 'terpene')"
    )
    conn.execute(
        "INSERT INTO molecules (id, name, molecule_type) VALUES (3, 'thc', 'cannabinoid')"
    )

    # Insert strains
    conn.execute(
        "INSERT INTO strains (id, name, normalized_name, strain_type, source) "
        "VALUES (1, 'Blue Dream', 'blue dream', 'hybrid', 'test')"
    )
    conn.execute(
        "INSERT INTO strains (id, name, normalized_name, strain_type, source) "
        "VALUES (2, 'OG Kush', 'og kush', 'indica', 'test')"
    )
    conn.execute(
        "INSERT INTO strains (id, name, normalized_name, strain_type, source) "
        "VALUES (3, 'Sour Diesel', 'sour diesel', 'sativa', 'test')"
    )
    # Strain 4: has compositions but NO effects (not ML-ready)
    conn.execute(
        "INSERT INTO strains (id, name, normalized_name, strain_type, source) "
        "VALUES (4, 'No Effects', 'no effects', 'hybrid', 'test')"
    )

    # Insert compositions (with some duplicates for averaging)
    compositions = [
        (1, 1, 0.5, "reported", "allbud"),   # Blue Dream: myrcene 0.5
        (1, 1, 0.7, "reported", "leafly"),    # Blue Dream: myrcene 0.7 (avg -> 0.6)
        (1, 2, 0.3, "reported", "allbud"),    # Blue Dream: limonene 0.3
        (1, 3, 22.0, "reported", "allbud"),   # Blue Dream: thc 22.0
        (2, 1, 0.4, "reported", "allbud"),    # OG Kush: myrcene 0.4
        (2, 3, 25.0, "reported", "allbud"),   # OG Kush: thc 25.0
        (3, 2, 0.8, "reported", "allbud"),    # Sour Diesel: limonene 0.8
        (3, 3, 20.0, "reported", "allbud"),   # Sour Diesel: thc 20.0
        (4, 1, 0.3, "reported", "allbud"),    # No Effects: myrcene (no effects)
    ]
    conn.executemany(
        "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, measurement_type, source) "
        "VALUES (?, ?, ?, ?, ?)",
        compositions,
    )

    # Get effect IDs from the effects table
    relaxed_id = conn.execute("SELECT id FROM effects WHERE name = 'relaxed'").fetchone()[0]
    euphoric_id = conn.execute("SELECT id FROM effects WHERE name = 'euphoric'").fetchone()[0]
    pain_id = conn.execute("SELECT id FROM effects WHERE name = 'pain'").fetchone()[0]

    effect_reports = [
        (1, relaxed_id, 100, "allbud"),
        (1, euphoric_id, 80, "allbud"),
        (1, pain_id, 50, "allbud"),
        (2, relaxed_id, 90, "allbud"),
        (2, pain_id, 70, "allbud"),
        (3, euphoric_id, 60, "allbud"),
    ]
    conn.executemany(
        "INSERT INTO effect_reports (strain_id, effect_id, report_count, source) "
        "VALUES (?, ?, ?, ?)",
        effect_reports,
    )

    conn.commit()
    conn.close()
    return db_path


class TestLoadFunctions:
    def test_load_molecules(self, ml_db):
        conn = sqlite3.connect(ml_db)
        df = load_molecules(conn)
        conn.close()
        assert len(df) == 3
        assert set(df["name"]) == {"myrcene", "limonene", "thc"}

    def test_load_effects(self, ml_db):
        conn = sqlite3.connect(ml_db)
        df = load_effects(conn)
        conn.close()
        assert len(df) == 52  # All canonical effects from taxonomy

    def test_load_ml_strain_ids(self, ml_db):
        conn = sqlite3.connect(ml_db)
        ids = load_ml_strain_ids(conn)
        conn.close()
        # Strains 1, 2, 3 have both compositions and effects; 4 has no effects
        assert set(ids) == {1, 2, 3}


class TestFeatureMatrix:
    def test_shape(self, ml_db):
        conn = sqlite3.connect(ml_db)
        molecules = load_molecules(conn)
        X = build_feature_matrix(conn, [1, 2, 3], molecules)
        conn.close()
        assert X.shape == (3, 3)  # 3 strains x 3 molecules

    def test_averaging_duplicates(self, ml_db):
        conn = sqlite3.connect(ml_db)
        molecules = load_molecules(conn)
        X = build_feature_matrix(conn, [1], molecules)
        conn.close()
        # Blue Dream myrcene: avg(0.5, 0.7) = 0.6
        assert abs(X.loc[1, "myrcene"] - 0.6) < 0.01

    def test_missing_filled_with_zero(self, ml_db):
        conn = sqlite3.connect(ml_db)
        molecules = load_molecules(conn)
        X = build_feature_matrix(conn, [2], molecules)
        conn.close()
        # OG Kush has no limonene
        assert X.loc[2, "limonene"] == 0.0

    def test_columns_sorted(self, ml_db):
        conn = sqlite3.connect(ml_db)
        molecules = load_molecules(conn)
        X = build_feature_matrix(conn, [1, 2, 3], molecules)
        conn.close()
        assert list(X.columns) == sorted(X.columns)


class TestLabelMatrix:
    def test_shape(self, ml_db):
        conn = sqlite3.connect(ml_db)
        effects = load_effects(conn)
        y = build_label_matrix(conn, [1, 2, 3], effects)
        conn.close()
        assert y.shape[0] == 3  # 3 strains
        assert y.shape[1] == 52  # all canonical effects from taxonomy

    def test_binary_values(self, ml_db):
        conn = sqlite3.connect(ml_db)
        effects = load_effects(conn)
        y = build_label_matrix(conn, [1, 2, 3], effects)
        conn.close()
        assert set(y.values.flatten()) <= {0, 1}

    def test_known_effects(self, ml_db):
        conn = sqlite3.connect(ml_db)
        effects = load_effects(conn)
        y = build_label_matrix(conn, [1, 2, 3], effects)
        conn.close()
        # Blue Dream: relaxed=1, euphoric=1, pain=1
        assert y.loc[1, "relaxed"] == 1
        assert y.loc[1, "euphoric"] == 1
        assert y.loc[1, "pain"] == 1
        # OG Kush: relaxed=1, euphoric=0
        assert y.loc[2, "relaxed"] == 1
        assert y.loc[2, "euphoric"] == 0
        # Sour Diesel: euphoric=1, relaxed=0
        assert y.loc[3, "euphoric"] == 1
        assert y.loc[3, "relaxed"] == 0

    def test_min_report_count_filter(self, ml_db):
        conn = sqlite3.connect(ml_db)
        effects = load_effects(conn)
        y = build_label_matrix(conn, [1, 2, 3], effects, min_report_count=75)
        conn.close()
        # Blue Dream relaxed=100 passes, euphoric=80 passes, pain=50 fails
        assert y.loc[1, "relaxed"] == 1
        assert y.loc[1, "euphoric"] == 1
        assert y.loc[1, "pain"] == 0


class TestBuildDataset:
    def test_end_to_end(self, ml_db):
        X, y, meta = build_dataset(ml_db, min_positive_strains=1)
        assert X.shape[0] == 3
        assert y.shape[0] == 3
        assert meta["n_strains"] == 3
        assert meta["n_features"] == 3

    def test_rare_effect_filtering(self, ml_db):
        # With min_positive_strains=3, only effects on all 3 strains survive
        X, y, meta = build_dataset(ml_db, min_positive_strains=3)
        # No single effect appears in all 3 test strains
        assert meta["n_effects_dropped"] > 0

    def test_metadata_keys(self, ml_db):
        _, _, meta = build_dataset(ml_db, min_positive_strains=1)
        expected_keys = {
            "n_strains", "n_features", "n_effects", "n_effects_dropped",
            "dropped_effects", "feature_names", "effect_names",
            "effect_positive_counts", "strain_types", "feature_fill_rate",
            "label_density",
        }
        assert expected_keys.issubset(set(meta.keys()))

    def test_strain4_excluded(self, ml_db):
        X, y, _ = build_dataset(ml_db, min_positive_strains=1)
        assert 4 not in X.index
        assert 4 not in y.index
