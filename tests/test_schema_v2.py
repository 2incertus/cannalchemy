import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db, DB_TABLES

def test_v2_tables_exist():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cur.fetchall()}
        conn.close()
        assert "canonical_effects" in tables
        assert "effect_mappings" in tables
        assert "strain_aliases" in tables

def test_effect_reports_has_confidence():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(effect_reports)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        assert "confidence" in columns

def test_canonical_effects_schema():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(canonical_effects)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        expected = {"id", "name", "category", "description", "synonyms", "receptor_pathway"}
        assert expected.issubset(columns)
