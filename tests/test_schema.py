import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db, DB_TABLES

def test_init_db_creates_all_tables():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cur.fetchall()}
        conn.close()
        for table in DB_TABLES:
            assert table in tables, f"Missing table: {table}"

def test_molecules_table_has_correct_columns():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(molecules)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        expected = {"id", "name", "smiles", "molecular_weight", "logp",
                    "tpsa", "molecule_type", "pubchem_cid", "inchikey"}
        assert expected.issubset(columns)

def test_init_db_is_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_db(db_path)
        init_db(db_path)  # Should not raise
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        count = cur.fetchone()[0]
        conn.close()
        assert count > 0
