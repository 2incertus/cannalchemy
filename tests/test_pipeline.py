import tempfile
import os
import pytest
from cannalchemy.data.pipeline import run_pipeline, PipelineConfig

STRAIN_TRACKER_DB = "/srv/appdata/strain-tracker/strain-tracker.db"

def test_pipeline_creates_database():
    if not os.path.exists(STRAIN_TRACKER_DB):
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "cannalchemy.db")
        config = PipelineConfig(
            db_path=db_path,
            strain_tracker_db=STRAIN_TRACKER_DB,
            skip_pubchem_api=True,  # Don't hit API in tests
        )
        stats = run_pipeline(config)
        assert os.path.exists(db_path)
        assert stats["strains_imported"] > 20000
        assert stats["receptors_created"] > 0
        assert stats["bindings_created"] > 0

def test_pipeline_without_strain_tracker():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "cannalchemy.db")
        config = PipelineConfig(
            db_path=db_path,
            strain_tracker_db=None,
            skip_pubchem_api=True,
        )
        stats = run_pipeline(config)
        assert os.path.exists(db_path)
        # Should still have molecules and receptors from seed data
        assert stats["receptors_created"] > 0
