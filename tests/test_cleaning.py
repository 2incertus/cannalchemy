"""Tests for the cleaning pipeline orchestrator."""
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.cleaning import run_cleaning_pipeline, CleaningConfig

STRAIN_TRACKER_DB = "/srv/appdata/strain-tracker/strain-tracker.db"

def test_cleaning_without_llm():
    """Test the cleaning pipeline with LLM disabled (rule-based only)."""
    if not os.path.exists(STRAIN_TRACKER_DB):
        import pytest
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        # First run the regular pipeline to populate data
        from cannalchemy.data.pipeline import run_pipeline, PipelineConfig
        run_pipeline(PipelineConfig(db_path=db_path, skip_pubchem_api=True))

        conn = sqlite3.connect(db_path)
        config = CleaningConfig(skip_llm=True, skip_dedup=True)
        stats = run_cleaning_pipeline(conn, config)
        conn.close()

        assert stats["canonical_effects_seeded"] > 50
        assert stats["molecules_added"] >= 0  # May be 0 if already expanded
        assert stats["rule_based"]["exact_matches"] >= 1

def test_cleaning_pipeline_creates_canonical_effects():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        # Insert a few test effects
        conn.execute("INSERT INTO effects (name, category) VALUES ('relaxed', 'positive')")
        conn.execute("INSERT INTO effects (name, category) VALUES ('euphoric', 'positive')")
        conn.commit()

        config = CleaningConfig(skip_llm=True, skip_dedup=True)
        stats = run_cleaning_pipeline(conn, config)
        count = conn.execute("SELECT COUNT(*) FROM canonical_effects").fetchone()[0]
        assert count > 50
        conn.close()
