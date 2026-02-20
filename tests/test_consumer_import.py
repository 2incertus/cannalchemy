"""Tests for consumer data importer (effect reports from scraped sources)."""
import pytest

from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import seed_canonical_effects
from cannalchemy.data.consumer_import import (
    import_effects_for_strain,
    import_consumer_batch,
)


@pytest.fixture
def db():
    conn = init_db(":memory:")
    seed_canonical_effects(conn)
    conn.execute(
        "INSERT INTO strains (name, normalized_name, strain_type, source) "
        "VALUES ('Blue Dream', 'blue dream', 'hybrid', 'strain-tracker')"
    )
    conn.commit()
    return conn


def test_import_effects_basic(db):
    effects = [
        {"canonical_id": 1, "canonical_name": "relaxed", "votes": 1000, "method": "exact"},
        {"canonical_id": 2, "canonical_name": "euphoric", "votes": 800, "method": "exact"},
    ]
    count = import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    assert count == 2
    rows = db.execute("SELECT * FROM effect_reports WHERE strain_id = 1").fetchall()
    assert len(rows) == 2


def test_import_effects_with_votes(db):
    effects = [
        {"canonical_id": 1, "canonical_name": "relaxed", "votes": 14858, "method": "exact"},
    ]
    import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    row = db.execute(
        "SELECT report_count, source FROM effect_reports WHERE strain_id = 1"
    ).fetchone()
    assert row[0] == 14858
    assert row[1] == "leafly"


def test_import_dedup_same_source(db):
    effects = [{"canonical_id": 1, "canonical_name": "relaxed", "votes": 100, "method": "exact"}]
    import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    count = db.execute(
        "SELECT COUNT(*) FROM effect_reports WHERE strain_id = 1 AND source = 'leafly'"
    ).fetchone()[0]
    assert count == 1


def test_import_different_sources(db):
    effects = [{"canonical_id": 1, "canonical_name": "relaxed", "votes": 100, "method": "exact"}]
    import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    import_effects_for_strain(db, strain_id=1, effects=effects, source="allbud")
    count = db.execute(
        "SELECT COUNT(*) FROM effect_reports WHERE strain_id = 1"
    ).fetchone()[0]
    assert count == 2


def test_import_batch(db):
    batch = [
        {
            "strain_id": 1,
            "source": "allbud",
            "effects": [
                {"canonical_id": 1, "canonical_name": "relaxed", "votes": 0, "method": "exact"},
                {"canonical_id": 3, "canonical_name": "happy", "votes": 0, "method": "exact"},
            ],
        },
    ]
    stats = import_consumer_batch(db, batch)
    assert stats["effects_imported"] == 2
    assert stats["strains_processed"] == 1
