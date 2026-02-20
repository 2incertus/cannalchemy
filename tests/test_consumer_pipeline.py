"""Tests for consumer pipeline orchestrator."""
import pytest

from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import seed_canonical_effects
from cannalchemy.data.consumer_pipeline import get_priority_strains


@pytest.fixture
def db():
    conn = init_db(":memory:")
    seed_canonical_effects(conn)
    for i, (name, source) in enumerate([
        ("Blue Dream", "strain-tracker"),
        ("OG Kush", "strain-tracker"),
        ("No Data", "strain-tracker"),
        ("Lab Only", "cannlytics"),
    ], start=1):
        conn.execute("INSERT INTO strains (id, name, normalized_name, strain_type, source) VALUES (?, ?, ?, 'hybrid', ?)", (i, name, name.lower(), source))
    conn.execute("INSERT INTO molecules (id, name, molecule_type) VALUES (1, 'myrcene', 'terpene')")
    conn.execute("INSERT INTO effects (id, name, category) VALUES (1, 'relaxed', 'positive')")
    # Blue Dream: has compositions + effects (already ML-ready)
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (1, 1, 0.5, 'test')")
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count, source) VALUES (1, 1, 10, 'strain-tracker')")
    # OG Kush: has compositions, no effects (priority target)
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (2, 1, 0.3, 'test')")
    # No Data: no compositions, no effects (skip)
    # Lab Only: cannlytics source (lower priority)
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (4, 1, 0.2, 'test')")
    conn.commit()
    return conn


def test_get_priority_strains(db):
    strains = get_priority_strains(db)
    names = [s["name"] for s in strains]
    assert "OG Kush" in names
    assert "Blue Dream" not in names  # already has effects
    assert "No Data" not in names     # no compositions


def test_priority_strains_include_fields(db):
    strains = get_priority_strains(db)
    for s in strains:
        assert "strain_type" in s
        assert "id" in s
        assert "name" in s
        assert "source" in s
