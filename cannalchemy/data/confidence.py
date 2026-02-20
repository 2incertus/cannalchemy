"""Confidence scoring for effect reports based on multi-source agreement and vote counts.

Recomputes confidence scores for all effect_reports rows using:
- Source agreement bonus: more independent sources confirming an effect = higher base
- Vote bonus: log-scaled normalization of report_count relative to the max
"""
import sqlite3
from math import log1p


def compute_confidence_scores(conn: sqlite3.Connection) -> dict:
    """Recompute confidence for ALL effect reports.

    Scoring formula per report:
        1. Count distinct sources for this (strain_id, effect_id) pair.
        2. Base + source bonus: 0.4 + min(n_sources - 1, 2) * 0.2
           - single source  = 0.4
           - dual sources    = 0.6
           - triple+ sources = 0.8
        3. Vote bonus (log-scaled, 0 to 0.2):
           log1p(report_count) / log1p(max_votes) * 0.2
        4. Cap at 1.0

    Args:
        conn: SQLite database connection.

    Returns:
        Dict with "updated" key: count of rows updated.
    """
    # Step 1: Get source count per (strain_id, effect_id) pair
    source_counts = {}
    rows = conn.execute(
        "SELECT strain_id, effect_id, COUNT(DISTINCT source) "
        "FROM effect_reports GROUP BY strain_id, effect_id"
    ).fetchall()
    for strain_id, effect_id, count in rows:
        source_counts[(strain_id, effect_id)] = count

    # Step 2: Get max votes for normalization
    max_row = conn.execute(
        "SELECT MAX(report_count) FROM effect_reports WHERE report_count > 0"
    ).fetchone()
    max_votes = max_row[0] if max_row and max_row[0] is not None else 0

    # Step 3: Compute and update each report's confidence
    all_reports = conn.execute(
        "SELECT id, strain_id, effect_id, report_count FROM effect_reports"
    ).fetchall()

    updated = 0
    for report_id, strain_id, effect_id, report_count in all_reports:
        n_sources = source_counts.get((strain_id, effect_id), 1)

        # Base + source bonus
        confidence = 0.4 + min(n_sources - 1, 2) * 0.2

        # Vote bonus (log-scaled, 0 to 0.2)
        if max_votes > 0 and report_count and report_count > 0:
            vote_bonus = log1p(report_count) / log1p(max_votes) * 0.2
            confidence += vote_bonus

        # Cap at 1.0
        confidence = min(confidence, 1.0)

        conn.execute(
            "UPDATE effect_reports SET confidence = ? WHERE id = ?",
            (confidence, report_id),
        )
        updated += 1

    conn.commit()
    return {"updated": updated}
