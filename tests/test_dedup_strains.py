"""Tests for strain name deduplication with fuzzy clustering."""
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.dedup_strains import find_duplicate_clusters, merge_strain_cluster


def test_find_duplicates_detects_near_matches():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'a')")
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream #1', 'blue dream 1', 'b')")
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('OG Kush', 'og kush', 'a')")
        conn.commit()
        clusters = find_duplicate_clusters(conn, threshold=85)
        # Blue Dream and Blue Dream #1 should be in a cluster
        assert len(clusters) >= 1
        blue_cluster = [c for c in clusters if any("blue dream" in n for n in c)]
        assert len(blue_cluster) == 1
        conn.close()


def test_merge_keeps_richest_strain():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'a')")
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream OG', 'blue dream og', 'b')")
        # Strain 1 has composition data, strain 2 doesn't
        conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage) VALUES (1, 1, 0.5)")
        conn.commit()
        merge_strain_cluster(conn, ["blue dream", "blue dream og"])
        # Should create alias pointing to the strain with more data
        alias = conn.execute("SELECT canonical_strain_id FROM strain_aliases").fetchone()
        assert alias is not None
        assert alias[0] == 1  # Strain with composition data is canonical
        conn.close()


def test_merge_is_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'a')")
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream OG', 'blue dream og', 'b')")
        conn.commit()
        merge_strain_cluster(conn, ["blue dream", "blue dream og"])
        merge_strain_cluster(conn, ["blue dream", "blue dream og"])  # Should not raise
        count = conn.execute("SELECT COUNT(*) FROM strain_aliases").fetchone()[0]
        assert count == 1
        conn.close()
