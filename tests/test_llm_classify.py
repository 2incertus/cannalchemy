"""Tests for effect classification (rule-based and LLM prompt/parse helpers)."""
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import CANONICAL_EFFECTS, seed_canonical_effects
from cannalchemy.data.llm_classify import (
    build_classification_prompt,
    parse_classification_response,
    classify_effects_rule_based,
)


def test_build_prompt_contains_canonical_names():
    prompt = build_classification_prompt(["relaxed", "some junk text here"])
    assert "relaxed" in prompt
    assert "euphoric" in prompt  # from canonical list
    assert "JUNK" in prompt


def test_parse_response_valid():
    response = '{"relaxed": "relaxed", "some junk": "JUNK", "pain relief": "pain"}'
    result = parse_classification_response(response)
    assert result["relaxed"] == "relaxed"
    assert result["some junk"] == "JUNK"
    assert result["pain relief"] == "pain"


def test_parse_response_handles_malformed():
    result = parse_classification_response("not json at all")
    assert result == {}


def test_rule_based_exact_match():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        seed_canonical_effects(conn)
        # Insert some raw effects
        conn.execute("INSERT INTO effects (name, category) VALUES ('relaxed', 'positive')")
        conn.execute("INSERT INTO effects (name, category) VALUES ('relaxing', 'positive')")
        conn.execute("INSERT INTO effects (name, category) VALUES ('total garbage sentence', 'positive')")
        conn.commit()
        stats = classify_effects_rule_based(conn)
        assert stats["exact_matches"] >= 1  # "relaxed" matches directly
        assert stats["synonym_matches"] >= 1  # "relaxing" matches via synonym
        conn.close()


def test_rule_based_maps_to_canonical():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        seed_canonical_effects(conn)
        conn.execute("INSERT INTO effects (name, category) VALUES ('cottonmouth', 'negative')")
        conn.commit()
        classify_effects_rule_based(conn)
        row = conn.execute(
            "SELECT em.raw_name, ce.name FROM effect_mappings em "
            "JOIN canonical_effects ce ON em.canonical_id = ce.id "
            "WHERE em.raw_name = 'cottonmouth'"
        ).fetchone()
        assert row is not None
        assert row[1] == "dry-mouth"
        conn.close()
