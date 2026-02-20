"""Tests for confidence scoring module."""
import pytest

from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import seed_canonical_effects
from cannalchemy.data.confidence import compute_confidence_scores


@pytest.fixture
def db():
    conn = init_db(":memory:")
    seed_canonical_effects(conn)
    conn.execute("INSERT INTO strains (name, normalized_name, strain_type, source) VALUES ('Test', 'test', 'hybrid', 'test')")
    # Need effects in the effects table too
    conn.execute("INSERT INTO effects (id, name, category) VALUES (1, 'relaxed', 'positive')")
    conn.execute("INSERT INTO effects (id, name, category) VALUES (2, 'euphoric', 'positive')")
    conn.execute("INSERT INTO effects (id, name, category) VALUES (3, 'happy', 'positive')")
    # Single-source effect
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) VALUES (1, 1, 100, 1.0, 'leafly')")
    # Multi-source effect (2 sources)
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) VALUES (1, 2, 50, 1.0, 'leafly')")
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) VALUES (1, 2, 0, 1.0, 'allbud')")
    # Triple-source effect
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) VALUES (1, 3, 200, 1.0, 'leafly')")
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) VALUES (1, 3, 0, 1.0, 'allbud')")
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) VALUES (1, 3, 50, 1.0, 'strain-tracker')")
    conn.commit()
    return conn


def test_multi_source_higher_confidence(db):
    stats = compute_confidence_scores(db)
    assert stats["updated"] > 0
    single = db.execute("SELECT confidence FROM effect_reports WHERE strain_id=1 AND effect_id=1 AND source='leafly'").fetchone()[0]
    multi = db.execute("SELECT confidence FROM effect_reports WHERE strain_id=1 AND effect_id=2 AND source='leafly'").fetchone()[0]
    triple = db.execute("SELECT confidence FROM effect_reports WHERE strain_id=1 AND effect_id=3 AND source='leafly'").fetchone()[0]
    assert multi > single
    assert triple >= multi


def test_vote_count_boosts_confidence(db):
    """Higher vote counts should produce a vote bonus within same source-count tier."""
    stats = compute_confidence_scores(db)
    assert stats["updated"] > 0
    # effect_id=1 has report_count=100 (single source, leafly)
    # effect_id=3 has report_count=200 (triple source, leafly) -- highest votes
    # The single-source high-vote (100) should still be less than multi-source,
    # but within the single-source tier, vote bonus should be > 0
    single = db.execute(
        "SELECT confidence FROM effect_reports WHERE strain_id=1 AND effect_id=1 AND source='leafly'"
    ).fetchone()[0]
    # Single source base = 0.4, with 100 votes out of max 200, vote bonus > 0
    assert single > 0.4, "Vote bonus should push single-source above 0.4 base"
    assert single <= 1.0, "Confidence should be capped at 1.0"


def test_confidence_returns_stats(db):
    stats = compute_confidence_scores(db)
    assert stats["updated"] == 6  # 6 total effect reports


def test_zero_votes_gets_base_only(db):
    """Reports with 0 votes should get only the base + source bonus, no vote bonus."""
    compute_confidence_scores(db)
    # effect_id=2, source=allbud has report_count=0, 2 sources
    zero_vote = db.execute(
        "SELECT confidence FROM effect_reports WHERE strain_id=1 AND effect_id=2 AND source='allbud'"
    ).fetchone()[0]
    # 2 sources = base 0.6, 0 votes = no vote bonus
    assert abs(zero_vote - 0.6) < 0.001, f"Expected ~0.6 for 2-source zero-vote, got {zero_vote}"
