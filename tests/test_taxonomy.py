"""Tests for the canonical effects taxonomy."""
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import CANONICAL_EFFECTS, seed_canonical_effects


def test_canonical_effects_has_three_categories():
    categories = {e["category"] for e in CANONICAL_EFFECTS}
    assert categories == {"positive", "negative", "medical"}


def test_canonical_effects_count():
    # Should have 51 canonical effects (20 positive + 12 negative + 19 medical)
    assert len(CANONICAL_EFFECTS) >= 50
    assert len(CANONICAL_EFFECTS) <= 90


def test_seed_canonical_effects():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        count = seed_canonical_effects(conn)
        assert count == len(CANONICAL_EFFECTS)
        # Verify in DB
        row = conn.execute("SELECT COUNT(*) FROM canonical_effects").fetchone()
        assert row[0] == len(CANONICAL_EFFECTS)
        conn.close()


def test_seed_is_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        seed_canonical_effects(conn)
        seed_canonical_effects(conn)  # Should not raise or duplicate
        row = conn.execute("SELECT COUNT(*) FROM canonical_effects").fetchone()
        assert row[0] == len(CANONICAL_EFFECTS)
        conn.close()


def test_positive_effects_exist():
    names = {e["name"] for e in CANONICAL_EFFECTS if e["category"] == "positive"}
    for expected in ["relaxed", "euphoric", "happy", "creative", "energetic", "focused"]:
        assert expected in names, f"Missing positive effect: {expected}"


def test_negative_effects_exist():
    names = {e["name"] for e in CANONICAL_EFFECTS if e["category"] == "negative"}
    for expected in ["dry-mouth", "dry-eyes", "paranoid", "anxious", "dizzy"]:
        assert expected in names, f"Missing negative effect: {expected}"


def test_medical_effects_exist():
    names = {e["name"] for e in CANONICAL_EFFECTS if e["category"] == "medical"}
    for expected in ["pain", "stress", "anxiety", "depression", "insomnia"]:
        assert expected in names, f"Missing medical effect: {expected}"
