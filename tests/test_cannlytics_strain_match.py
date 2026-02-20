"""Tests for Cannlytics strain cross-reference with fuzzy matching."""
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.cannlytics_strain_match import (
    normalize_lab_results,
    match_strains,
)

def test_normalize_lab_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute(
            "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
            "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
            ("Blue Dream (1g)", "", "NV", "myrcene", 0.65, "percent"),
        )
        conn.commit()
        count = normalize_lab_results(conn)
        assert count >= 1
        row = conn.execute("SELECT normalized_strain_name FROM lab_results").fetchone()
        assert row[0] == "blue dream 1g"
        conn.close()

def test_match_existing_strains():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'strain-tracker')")
        conn.execute(
            "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
            "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
            ("Blue Dream Hybrid", "blue dream hybrid", "NV", "myrcene", 0.65, "percent"),
        )
        conn.commit()
        stats = match_strains(conn, threshold=80)
        assert stats["matched"] >= 1 or stats["created"] >= 1
        conn.close()

def test_creates_new_strains():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute(
            "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
            "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
            ("Totally Unique Strain XYZ", "totally unique strain xyz", "NV", "myrcene", 0.65, "percent"),
        )
        conn.commit()
        stats = match_strains(conn, threshold=90)
        assert stats["created"] >= 1
        row = conn.execute("SELECT * FROM strains WHERE source='cannlytics'").fetchone()
        assert row is not None
        conn.close()
