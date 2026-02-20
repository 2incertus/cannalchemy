"""Match Cannlytics lab strain names to existing strains or create new ones."""
import sqlite3
from rapidfuzz import fuzz, process
from cannalchemy.data.normalize import normalize_strain_name


def normalize_lab_results(conn: sqlite3.Connection) -> int:
    """Normalize all strain names in lab_results that haven't been normalized yet.

    Returns count of rows updated.
    """
    rows = conn.execute(
        "SELECT id, strain_name FROM lab_results WHERE normalized_strain_name = ''"
    ).fetchall()

    count = 0
    for row_id, strain_name in rows:
        normalized = normalize_strain_name(strain_name)
        if normalized:
            conn.execute(
                "UPDATE lab_results SET normalized_strain_name = ? WHERE id = ?",
                (normalized, row_id),
            )
            count += 1

    conn.commit()
    return count


def match_strains(conn: sqlite3.Connection, threshold: int = 90, fuzzy: bool = True) -> dict:
    """Match lab result strain names to existing strains or create new ones.

    For large datasets (>1000 distinct names), set fuzzy=False to skip
    the O(n*m) fuzzy matching and only do exact matching + creation.
    Fuzzy matching is too slow for 40K+ names against 24K+ strains.

    Returns stats dict with matched, created, skipped counts.
    """
    stats = {"matched": 0, "created": 0, "skipped": 0, "fuzzy_matched": 0}

    existing = conn.execute(
        "SELECT id, normalized_name FROM strains"
    ).fetchall()
    existing_map = {row[1]: row[0] for row in existing}
    existing_names = list(existing_map.keys()) if fuzzy else []

    lab_names = conn.execute(
        "SELECT DISTINCT normalized_strain_name FROM lab_results "
        "WHERE normalized_strain_name != ''"
    ).fetchall()
    lab_names = [row[0] for row in lab_names]

    for i, lab_name in enumerate(lab_names):
        if lab_name in existing_map:
            stats["matched"] += 1
            continue

        if fuzzy and existing_names:
            match = process.extractOne(
                lab_name, existing_names,
                scorer=fuzz.ratio,
                score_cutoff=threshold,
            )
            if match:
                stats["fuzzy_matched"] += 1
                stats["matched"] += 1
                continue

        cur = conn.execute(
            "INSERT OR IGNORE INTO strains (name, normalized_name, strain_type, source) "
            "VALUES (?, ?, 'unknown', 'cannlytics')",
            (lab_name, lab_name),
        )
        if cur.rowcount == 1:
            stats["created"] += 1
            existing_map[lab_name] = cur.lastrowid
        else:
            stats["skipped"] += 1

        if (i + 1) % 5000 == 0:
            conn.commit()
            print(f"  Progress: {i+1}/{len(lab_names)} "
                  f"(matched={stats['matched']}, created={stats['created']})")

    conn.commit()
    return stats
