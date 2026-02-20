"""Import scraped consumer effect data into the Cannalchemy database.

Handles inserting effect reports from sources like Leafly and AllBud,
mapping canonical effect IDs to the effects table and deduplicating
by (strain_id, effect_id, source) unique constraint.
"""
import sqlite3
from typing import List, Dict, Any


def _ensure_effect_exists(
    conn: sqlite3.Connection,
    canonical_id: int,
    canonical_name: str,
) -> int:
    """Ensure the canonical effect exists in the effects table.

    Looks up the category from canonical_effects, inserts into effects
    if not already present, and returns the effects table ID.
    """
    # Check if already in effects table
    row = conn.execute(
        "SELECT id FROM effects WHERE name = ?", (canonical_name,)
    ).fetchone()
    if row:
        return row[0]

    # Look up category from canonical_effects
    ce_row = conn.execute(
        "SELECT category FROM canonical_effects WHERE id = ?", (canonical_id,)
    ).fetchone()
    category = ce_row[0] if ce_row else "other"

    conn.execute(
        "INSERT OR IGNORE INTO effects (name, category) VALUES (?, ?)",
        (canonical_name, category),
    )
    row = conn.execute(
        "SELECT id FROM effects WHERE name = ?", (canonical_name,)
    ).fetchone()
    return row[0]


def import_effects_for_strain(
    conn: sqlite3.Connection,
    strain_id: int,
    effects: List[Dict[str, Any]],
    source: str,
) -> int:
    """Import effect reports for a single strain.

    Args:
        conn: SQLite database connection.
        strain_id: ID of the strain in the strains table.
        effects: List of dicts with keys: canonical_id, canonical_name,
                 votes, method.
        source: Data source identifier (e.g. "leafly", "allbud").

    Returns:
        Count of new records inserted.
    """
    inserted = 0
    for effect in effects:
        effect_id = _ensure_effect_exists(
            conn,
            effect["canonical_id"],
            effect["canonical_name"],
        )
        report_count = effect.get("votes", 0)
        cur = conn.execute(
            "INSERT OR IGNORE INTO effect_reports "
            "(strain_id, effect_id, report_count, confidence, source) "
            "VALUES (?, ?, ?, 1.0, ?)",
            (strain_id, effect_id, report_count, source),
        )
        if cur.rowcount == 1:
            inserted += 1
    conn.commit()
    return inserted


def import_consumer_batch(
    conn: sqlite3.Connection,
    batch: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Import a batch of consumer effect data for multiple strains.

    Args:
        conn: SQLite database connection.
        batch: List of dicts with keys: strain_id, source, effects.

    Returns:
        Stats dict with keys: strains_processed, effects_imported, skipped.
    """
    stats = {"strains_processed": 0, "effects_imported": 0, "skipped": 0}

    for item in batch:
        count = import_effects_for_strain(
            conn,
            strain_id=item["strain_id"],
            effects=item["effects"],
            source=item["source"],
        )
        stats["strains_processed"] += 1
        stats["effects_imported"] += count
        stats["skipped"] += len(item["effects"]) - count

    return stats
