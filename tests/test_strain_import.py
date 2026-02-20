import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.strain_import import import_from_strain_tracker

# Path to the real strain-tracker DB
STRAIN_TRACKER_DB = "/srv/appdata/strain-tracker/strain-tracker.db"

def test_import_creates_strains():
    """Test that import populates strains table from strain-tracker."""
    if not os.path.exists(STRAIN_TRACKER_DB):
        import pytest
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        stats = import_from_strain_tracker(conn, STRAIN_TRACKER_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM strains")
        count = cur.fetchone()[0]
        conn.close()
        assert count > 20000  # We know there are 25K+
        assert stats["strains_imported"] > 20000

def test_import_creates_molecules():
    """Test that terpenes are imported as molecules."""
    if not os.path.exists(STRAIN_TRACKER_DB):
        import pytest
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        import_from_strain_tracker(conn, STRAIN_TRACKER_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM molecules WHERE molecule_type='terpene'")
        count = cur.fetchone()[0]
        conn.close()
        assert count >= 18  # 20 terpenes minus 'null' and other junk

def test_import_creates_strain_compositions():
    """Test that terpene percentages are linked to strains."""
    if not os.path.exists(STRAIN_TRACKER_DB):
        import pytest
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        import_from_strain_tracker(conn, STRAIN_TRACKER_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM strain_compositions")
        count = cur.fetchone()[0]
        conn.close()
        assert count > 50000  # 68K terpene rows minus junk

def test_import_creates_effects():
    """Test that effects are imported."""
    if not os.path.exists(STRAIN_TRACKER_DB):
        import pytest
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        import_from_strain_tracker(conn, STRAIN_TRACKER_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM effects")
        count = cur.fetchone()[0]
        conn.close()
        assert count >= 10  # At least 10 effects
