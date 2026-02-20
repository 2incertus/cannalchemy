"""Tests for lab-to-composition aggregation."""
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.cannlytics_aggregate import aggregate_lab_to_compositions

def test_aggregate_computes_median():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'cannlytics')")
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
        for val in [0.5, 0.6, 0.7]:
            conn.execute(
                "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
                "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
                ("Blue Dream", "blue dream", "NV", "myrcene", val, "percent"),
            )
        conn.commit()
        stats = aggregate_lab_to_compositions(conn)
        assert stats["compositions_created"] >= 1
        row = conn.execute(
            "SELECT percentage FROM strain_compositions WHERE measurement_type='lab_tested'"
        ).fetchone()
        assert row is not None
        assert abs(row[0] - 0.6) < 0.01
        conn.close()

def test_aggregate_tags_existing_as_reported():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'st')")
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
        conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (1, 1, 0.5, 'strain-tracker')")
        conn.commit()
        stats = aggregate_lab_to_compositions(conn)
        row = conn.execute(
            "SELECT measurement_type FROM strain_compositions WHERE source='strain-tracker'"
        ).fetchone()
        assert row[0] == "reported"
        conn.close()

def test_aggregate_keeps_both():
    """Lab data should coexist with reported data, not replace it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'st')")
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
        conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (1, 1, 0.5, 'strain-tracker')")
        conn.execute(
            "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
            "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
            ("Blue Dream", "blue dream", "NV", "myrcene", 0.7, "percent"),
        )
        conn.commit()
        aggregate_lab_to_compositions(conn)
        count = conn.execute(
            "SELECT COUNT(*) FROM strain_compositions WHERE strain_id=1 AND molecule_id=1"
        ).fetchone()[0]
        assert count == 2  # both reported and lab_tested
        conn.close()
