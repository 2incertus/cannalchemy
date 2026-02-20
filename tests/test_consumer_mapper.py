"""Tests for consumer effect name mapper."""
import pytest
from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import seed_canonical_effects
from cannalchemy.data.consumer_mapper import (
    build_effect_lookup,
    map_effect_name,
    map_effects_batch,
)


@pytest.fixture
def db():
    conn = init_db(":memory:")
    seed_canonical_effects(conn)
    return conn


def test_build_lookup_from_db(db):
    lookup = build_effect_lookup(db)
    assert "relaxed" in lookup
    assert "dry-mouth" in lookup
    assert "pain" in lookup
    assert len(lookup) >= 51


def test_map_exact_match(db):
    lookup = build_effect_lookup(db)
    result = map_effect_name("Happy", lookup)
    assert result is not None
    assert result["canonical_name"] == "happy"
    assert result["method"] == "exact"


def test_map_with_spaces(db):
    lookup = build_effect_lookup(db)
    result = map_effect_name("Dry Mouth", lookup)
    assert result is not None
    assert result["canonical_name"] == "dry-mouth"


def test_map_synonym(db):
    lookup = build_effect_lookup(db)
    result = map_effect_name("Cottonmouth", lookup)
    assert result is not None
    assert result["canonical_name"] == "dry-mouth"
    assert result["method"] == "synonym"


def test_map_medical(db):
    lookup = build_effect_lookup(db)
    result = map_effect_name("Stress", lookup)
    assert result is not None
    assert result["canonical_name"] == "stress"


def test_map_unknown_returns_none(db):
    lookup = build_effect_lookup(db)
    result = map_effect_name("xyznonexistent", lookup)
    assert result is None


def test_map_batch(db):
    lookup = build_effect_lookup(db)
    names = ["Happy", "Creative", "Dry Mouth", "Stress", "nonsense"]
    results = map_effects_batch(names, lookup)
    assert len(results["mapped"]) == 4
    assert len(results["unmapped"]) == 1
    assert "nonsense" in results["unmapped"]


def test_map_lack_of_appetite(db):
    """'Lack of Appetite' -> 'lack-of-appetite'."""
    lookup = build_effect_lookup(db)
    result = map_effect_name("Lack of Appetite", lookup)
    assert result is not None
    assert result["canonical_name"] == "lack-of-appetite"
