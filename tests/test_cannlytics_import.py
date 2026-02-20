"""Tests for Cannlytics lab results import pipeline."""
import sqlite3
import tempfile
import os
import json
import pandas as pd
from cannalchemy.data.schema import init_db
from cannalchemy.data.cannlytics_import import import_state_data

def _make_csv(tmpdir, rows):
    """Create a test CSV file."""
    path = os.path.join(tmpdir, "test.csv")
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return path

def test_import_flat_data():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        csv_path = _make_csv(tmpdir, [
            {"product_name": "Blue Dream", "beta_myrcene": 0.65, "alpha_pinene": 0.12,
             "d_limonene": 0.45, "delta_9_thc": 22.5, "date_tested": "2023-01-15"},
            {"product_name": "OG Kush", "beta_myrcene": 0.33, "alpha_pinene": 0.08,
             "d_limonene": 0.21, "delta_9_thc": 25.0, "date_tested": "2023-01-16"},
        ])
        stats = import_state_data(conn, csv_path, "nv", format_type="flat",
                                  strain_field="product_name")
        assert stats["rows_processed"] == 2
        assert stats["measurements_inserted"] > 0
        count = conn.execute("SELECT COUNT(*) FROM lab_results").fetchone()[0]
        assert count > 0
        conn.close()

def test_import_json_results_data():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        results_json = json.dumps([
            {"key": "beta_myrcene", "value": 0.65, "units": "percent"},
            {"key": "delta_9_thc", "value": 22.5, "units": "percent"},
        ])
        csv_path = _make_csv(tmpdir, [
            {"product_name": "Blue Dream", "results": results_json, "date_tested": "2023-01-15"},
        ])
        stats = import_state_data(conn, csv_path, "ca", format_type="json_results",
                                  strain_field="product_name")
        assert stats["rows_processed"] == 1
        assert stats["measurements_inserted"] >= 2
        conn.close()

def test_import_skips_empty_rows():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        csv_path = _make_csv(tmpdir, [
            {"product_name": "No Data Strain", "date_tested": "2023-01-15"},
        ])
        stats = import_state_data(conn, csv_path, "nv", format_type="flat",
                                  strain_field="product_name")
        assert stats["rows_skipped"] == 1
        conn.close()

def test_import_records_provenance():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        csv_path = _make_csv(tmpdir, [
            {"product_name": "Test", "beta_myrcene": 0.5, "date_tested": "2023-01-15"},
        ])
        import_state_data(conn, csv_path, "nv", format_type="flat",
                          strain_field="product_name")
        row = conn.execute("SELECT state FROM lab_results LIMIT 1").fetchone()
        assert row is not None
        assert row[0] == "NV"
        conn.close()
