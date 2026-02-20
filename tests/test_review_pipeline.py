"""Tests for the review import pipeline."""
import sqlite3
from pathlib import Path

import pytest

from cannalchemy.data.review_pipeline import (
    build_name_mapping,
    load_reviews_by_strain,
    run_pipeline,
)
from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import seed_canonical_effects


@pytest.fixture
def cannalchemy_db(tmp_path):
    """Create a Cannalchemy DB with schema, canonical effects, and test strains."""
    db_path = str(tmp_path / "cannalchemy.db")
    conn = init_db(db_path)
    seed_canonical_effects(conn)
    # Insert test strains
    conn.execute(
        "INSERT INTO strains (name, normalized_name, strain_type, source) "
        "VALUES ('Blue Dream', 'blue dream', 'hybrid', 'strain-tracker')"
    )
    conn.execute(
        "INSERT INTO strains (name, normalized_name, strain_type, source) "
        "VALUES ('OG Kush', 'og kush', 'indica', 'strain-tracker')"
    )
    conn.execute(
        "INSERT INTO strains (name, normalized_name, strain_type, source) "
        "VALUES ('Sour Diesel', 'sour diesel', 'sativa', 'strain-tracker')"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def st_db(tmp_path):
    """Create a mock Strain Tracker DB with strains and reviews."""
    db_path = str(tmp_path / "strain-tracker.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE strains (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE external_reviews (
            id INTEGER PRIMARY KEY,
            strain_id INTEGER NOT NULL,
            source TEXT DEFAULT 'leafly',
            review_text TEXT DEFAULT '',
            FOREIGN KEY (strain_id) REFERENCES strains(id)
        )
    """)
    # Insert strains
    conn.execute("INSERT INTO strains (id, name) VALUES (1, 'Blue Dream')")
    conn.execute("INSERT INTO strains (id, name) VALUES (2, 'OG Kush')")
    conn.execute("INSERT INTO strains (id, name) VALUES (3, 'Unknown Strain XYZ')")

    # Insert reviews
    reviews = [
        (1, "leafly", "Made me feel very relaxed and happy. Great for pain relief."),
        (1, "leafly", "Euphoric high, super creative. A bit of dry mouth though."),
        (1, "leafly", "Chill vibes, felt calm and uplifted. Helped with my stress."),
        (2, "leafly", "Strong body high, very sleepy. Good for insomnia."),
        (2, "leafly", "Got the munchies bad. Felt relaxed but dizzy at first."),
        (3, "leafly", "Just a great strain overall, nice effects."),
    ]
    conn.executemany(
        "INSERT INTO external_reviews (strain_id, source, review_text) VALUES (?, ?, ?)",
        reviews,
    )
    conn.commit()
    conn.close()
    return db_path


class TestLoadReviews:
    def test_loads_grouped_by_strain(self, st_db):
        result = load_reviews_by_strain(st_db)
        assert "Blue Dream" in result
        assert "OG Kush" in result
        assert len(result["Blue Dream"]) == 3
        assert len(result["OG Kush"]) == 2

    def test_includes_strain_with_short_reviews(self, st_db):
        result = load_reviews_by_strain(st_db)
        assert "Unknown Strain XYZ" in result


class TestNameMapping:
    def test_case_insensitive_matching(self, cannalchemy_db):
        conn = init_db(cannalchemy_db)
        mapping = build_name_mapping(conn)
        assert "blue dream" in mapping
        assert "og kush" in mapping
        assert "sour diesel" in mapping
        conn.close()


class TestPipeline:
    def test_end_to_end(self, cannalchemy_db, st_db, tmp_path):
        pf = tmp_path / "progress_e2e.json"
        stats = run_pipeline(cannalchemy_db, st_db, progress_file=pf)
        assert stats["strains_with_reviews"] == 3
        assert stats["strains_matched"] >= 2  # Blue Dream and OG Kush
        assert stats["strains_enriched"] >= 1
        assert stats["effects_imported"] > 0

    def test_with_limit(self, cannalchemy_db, st_db, tmp_path):
        pf = tmp_path / "progress_limit.json"
        stats = run_pipeline(cannalchemy_db, st_db, limit=1, progress_file=pf)
        assert stats["strains_enriched"] <= 1

    def test_effects_in_db(self, cannalchemy_db, st_db, tmp_path):
        pf = tmp_path / "progress_db.json"
        run_pipeline(cannalchemy_db, st_db, progress_file=pf)
        conn = sqlite3.connect(cannalchemy_db)
        rows = conn.execute(
            "SELECT source, COUNT(*) FROM effect_reports WHERE source = 'leafly-reviews' GROUP BY source"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "leafly-reviews"
        assert rows[0][1] > 0
        conn.close()

    def test_confidence_recomputed(self, cannalchemy_db, st_db, tmp_path):
        pf = tmp_path / "progress_conf.json"
        run_pipeline(cannalchemy_db, st_db, progress_file=pf)
        conn = sqlite3.connect(cannalchemy_db)
        rows = conn.execute(
            "SELECT confidence FROM effect_reports WHERE source = 'leafly-reviews'"
        ).fetchall()
        assert all(0 < r[0] <= 1.0 for r in rows)
        conn.close()

    def test_idempotent_reimport(self, cannalchemy_db, st_db, tmp_path):
        """Running twice should not duplicate effect_reports."""
        pf = tmp_path / "progress_idem.json"
        stats1 = run_pipeline(cannalchemy_db, st_db, progress_file=pf)
        assert stats1["effects_imported"] > 0
        # Clear progress to force reprocessing
        pf.unlink()
        stats2 = run_pipeline(cannalchemy_db, st_db, progress_file=pf)
        # Second run should import 0 new effects (UNIQUE constraint)
        assert stats2["effects_imported"] == 0
