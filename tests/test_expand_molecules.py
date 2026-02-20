"""Tests for expand_molecules: adding CBN, CBG, CBC, THCV with bindings."""
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.expand_molecules import expand_cannabinoids


def test_expand_adds_missing_cannabinoids():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        # Seed just THC and CBD (like Phase 1 import does)
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('thc', 'cannabinoid')")
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('cbd', 'cannabinoid')")
        conn.commit()
        stats = expand_cannabinoids(conn)
        # Should now have 6 total cannabinoids
        count = conn.execute("SELECT COUNT(*) FROM molecules WHERE molecule_type='cannabinoid'").fetchone()[0]
        assert count == 6
        assert stats["molecules_added"] == 4  # CBN, CBG, CBC, THCV
        conn.close()


def test_expand_seeds_bindings():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        # Seed molecules
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('thc', 'cannabinoid')")
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('cbd', 'cannabinoid')")
        conn.commit()
        stats = expand_cannabinoids(conn)
        # Should have CBN and CBG bindings
        cbn_bindings = conn.execute(
            "SELECT COUNT(*) FROM binding_affinities ba "
            "JOIN molecules m ON ba.molecule_id = m.id WHERE m.name = 'cbn'"
        ).fetchone()[0]
        assert cbn_bindings >= 2  # CB1 + CB2
        conn.close()


def test_expand_has_smiles():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        stats = expand_cannabinoids(conn)
        # All cannabinoids should have SMILES
        missing = conn.execute(
            "SELECT name FROM molecules WHERE molecule_type='cannabinoid' AND (smiles='' OR smiles IS NULL)"
        ).fetchall()
        assert len(missing) == 0, f"Missing SMILES: {[r[0] for r in missing]}"
        conn.close()


def test_expand_is_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        expand_cannabinoids(conn)
        expand_cannabinoids(conn)  # Should not raise or duplicate
        count = conn.execute("SELECT COUNT(*) FROM molecules WHERE molecule_type='cannabinoid'").fetchone()[0]
        assert count == 6
        conn.close()
