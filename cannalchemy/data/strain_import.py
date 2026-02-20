"""Import data from the Strain Tracker SQLite database."""
import json
import sqlite3
from cannalchemy.data.normalize import normalize_strain_name

# Known terpenes — skip 'null' and other junk entries
VALID_TERPENES = {
    "bisabolol", "borneol", "camphene", "carene", "caryophyllene",
    "eucalyptol", "farnesene", "fenchol", "geraniol", "guaiol",
    "humulene", "limonene", "linalool", "myrcene", "nerolidol",
    "ocimene", "phellandrene", "pinene", "terpineol", "terpinolene",
    "valencene",
}


def import_from_strain_tracker(
    dest_conn: sqlite3.Connection,
    source_db_path: str,
) -> dict:
    """Import strains, terpenes, effects from strain-tracker DB.

    Returns dict with import statistics.
    """
    src = sqlite3.connect(source_db_path)
    src.row_factory = sqlite3.Row
    stats = {
        "strains_imported": 0,
        "molecules_created": 0,
        "compositions_created": 0,
        "effects_created": 0,
        "effect_reports_created": 0,
        "skipped_null_terpenes": 0,
    }

    # Track source
    dest_conn.execute(
        "INSERT OR IGNORE INTO data_sources (name, source_type, url) VALUES (?, ?, ?)",
        ("strain-tracker", "local_db", source_db_path),
    )

    # 1. Import terpenes as molecules
    terpene_id_map = {}
    for terpene_name in VALID_TERPENES:
        cur = dest_conn.execute(
            "INSERT OR IGNORE INTO molecules (name, molecule_type) VALUES (?, 'terpene')",
            (terpene_name,),
        )
        if cur.lastrowid:
            stats["molecules_created"] += 1
        # Get the ID (whether just inserted or already existed)
        row = dest_conn.execute(
            "SELECT id FROM molecules WHERE name = ?", (terpene_name,)
        ).fetchone()
        terpene_id_map[terpene_name] = row[0]

    # Also create THC and CBD as cannabinoid molecules
    for cann in ["thc", "cbd"]:
        dest_conn.execute(
            "INSERT OR IGNORE INTO molecules (name, molecule_type) VALUES (?, 'cannabinoid')",
            (cann,),
        )
        row = dest_conn.execute(
            "SELECT id FROM molecules WHERE name = ?", (cann,)
        ).fetchone()
        terpene_id_map[cann] = row[0]
        stats["molecules_created"] += 1

    # 2. Import effects taxonomy
    effect_id_map = {}
    src_strains = src.execute("SELECT effects, negatives, medical FROM strains").fetchall()
    all_effects = set()
    all_negatives = set()
    all_medical = set()

    for row in src_strains:
        for field, target_set in [(row["effects"], all_effects),
                                   (row["negatives"], all_negatives),
                                   (row["medical"], all_medical)]:
            if field and field != "[]":
                try:
                    items = json.loads(field)
                    target_set.update(e.strip().lower() for e in items if e.strip())
                except (json.JSONDecodeError, TypeError):
                    pass

    for effect_name in all_effects:
        dest_conn.execute(
            "INSERT OR IGNORE INTO effects (name, category) VALUES (?, 'positive')",
            (effect_name,),
        )
    for neg in all_negatives:
        dest_conn.execute(
            "INSERT OR IGNORE INTO effects (name, category) VALUES (?, 'negative')",
            (neg,),
        )
    for med in all_medical:
        dest_conn.execute(
            "INSERT OR IGNORE INTO effects (name, category) VALUES (?, 'medical')",
            (med,),
        )

    # Build effect ID map
    for row in dest_conn.execute("SELECT id, name FROM effects").fetchall():
        effect_id_map[row[1]] = row[0]

    stats["effects_created"] = len(effect_id_map)

    # 3. Import strains
    src_strains = src.execute(
        "SELECT id, name, type, thc_min, thc_max, cbd_min, cbd_max, "
        "description, effects, flavors, negatives, medical, image_url "
        "FROM strains"
    ).fetchall()

    strain_id_map = {}  # source_id -> dest_id

    for s in src_strains:
        normalized = normalize_strain_name(s["name"])
        cur = dest_conn.execute(
            "INSERT OR IGNORE INTO strains "
            "(name, normalized_name, strain_type, description, image_url, source, source_id) "
            "VALUES (?, ?, ?, ?, ?, 'strain-tracker', ?)",
            (s["name"], normalized,
             s["type"] if s["type"] in ("indica", "sativa", "hybrid") else "unknown",
             s["description"] or "", s["image_url"] or "", str(s["id"])),
        )
        if cur.rowcount == 1:
            strain_id_map[s["id"]] = cur.lastrowid
            stats["strains_imported"] += 1
        else:
            # Duplicate normalized_name — look up the existing row
            row = dest_conn.execute(
                "SELECT id FROM strains WHERE normalized_name = ? AND source = 'strain-tracker'",
                (normalized,),
            ).fetchone()
            if row:
                strain_id_map[s["id"]] = row[0]

        dest_id = strain_id_map.get(s["id"])
        if not dest_id:
            continue

        # Import THC/CBD as compositions (use max value as representative)
        if s["thc_max"] and s["thc_max"] > 0:
            dest_conn.execute(
                "INSERT OR IGNORE INTO strain_compositions "
                "(strain_id, molecule_id, percentage, measurement_type, source) "
                "VALUES (?, ?, ?, 'reported', 'strain-tracker')",
                (dest_id, terpene_id_map["thc"], s["thc_max"]),
            )
            stats["compositions_created"] += 1

        if s["cbd_max"] and s["cbd_max"] > 0:
            dest_conn.execute(
                "INSERT OR IGNORE INTO strain_compositions "
                "(strain_id, molecule_id, percentage, measurement_type, source) "
                "VALUES (?, ?, ?, 'reported', 'strain-tracker')",
                (dest_id, terpene_id_map["cbd"], s["cbd_max"]),
            )
            stats["compositions_created"] += 1

        # Import effect reports
        for field_name in ("effects", "negatives", "medical"):
            field_val = s[field_name] if field_name in s.keys() else None
            if field_val and field_val != "[]":
                try:
                    items = json.loads(field_val)
                    for effect_name in items:
                        ename = effect_name.strip().lower()
                        eid = effect_id_map.get(ename)
                        if eid:
                            dest_conn.execute(
                                "INSERT OR IGNORE INTO effect_reports "
                                "(strain_id, effect_id, report_count, source) "
                                "VALUES (?, ?, 1, 'strain-tracker')",
                                (dest_id, eid),
                            )
                            stats["effect_reports_created"] += 1
                except (json.JSONDecodeError, TypeError):
                    pass

    # 4. Import terpene compositions
    src_terpenes = src.execute(
        "SELECT strain_id, terpene_name, percentage FROM strain_terpenes "
        "WHERE terpene_name != 'null' AND percentage > 0"
    ).fetchall()

    for t in src_terpenes:
        dest_strain_id = strain_id_map.get(t["strain_id"])
        terpene_name = t["terpene_name"].lower().strip()
        molecule_id = terpene_id_map.get(terpene_name)

        if not dest_strain_id or not molecule_id:
            stats["skipped_null_terpenes"] += 1
            continue

        dest_conn.execute(
            "INSERT OR IGNORE INTO strain_compositions "
            "(strain_id, molecule_id, percentage, measurement_type, source) "
            "VALUES (?, ?, ?, 'reported', 'strain-tracker')",
            (dest_strain_id, molecule_id, t["percentage"]),
        )
        stats["compositions_created"] += 1

    dest_conn.commit()
    src.close()
    return stats
