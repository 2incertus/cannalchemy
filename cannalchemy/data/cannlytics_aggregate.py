"""Aggregate lab_results into strain_compositions using median."""
import sqlite3
import statistics


def aggregate_lab_to_compositions(conn: sqlite3.Connection) -> dict:
    """Aggregate lab results into strain_compositions.

    - Tags existing compositions as 'reported'
    - Computes median per (strain, molecule) from lab_results
    - Inserts new compositions as 'lab_tested'
    - Keeps both reported and lab_tested (user decision: coexist)

    Returns stats dict.
    """
    stats = {
        "existing_tagged": 0,
        "compositions_created": 0,
        "strains_enriched": 0,
    }

    # 1. Tag existing compositions as 'reported' if not already tagged
    updated = conn.execute(
        "UPDATE strain_compositions SET measurement_type = 'reported' "
        "WHERE measurement_type = '' OR measurement_type IS NULL"
    ).rowcount
    stats["existing_tagged"] = updated

    # 2. Get molecule ID map
    molecule_ids = {}
    for row in conn.execute("SELECT id, name FROM molecules"):
        molecule_ids[row[1]] = row[0]

    # 3. Get strain ID map (normalized_name -> id)
    strain_ids = {}
    for row in conn.execute("SELECT id, normalized_name FROM strains"):
        strain_ids[row[1]] = row[0]

    # 4. Group lab results by (normalized_strain_name, molecule_name)
    lab_data = conn.execute(
        "SELECT normalized_strain_name, molecule_name, concentration "
        "FROM lab_results WHERE concentration IS NOT NULL "
        "AND normalized_strain_name != ''"
    ).fetchall()

    groups = {}
    for norm_name, mol_name, conc in lab_data:
        key = (norm_name, mol_name)
        if key not in groups:
            groups[key] = []
        groups[key].append(conc)

    # 5. Compute median and insert
    enriched_strains = set()
    for (norm_name, mol_name), values in groups.items():
        strain_id = strain_ids.get(norm_name)
        molecule_id = molecule_ids.get(mol_name)
        if not strain_id or not molecule_id:
            continue

        median_val = statistics.median(values)
        sample_count = len(values)

        existing = conn.execute(
            "SELECT id FROM strain_compositions "
            "WHERE strain_id=? AND molecule_id=? AND measurement_type='lab_tested'",
            (strain_id, molecule_id),
        ).fetchone()

        if existing:
            continue

        conn.execute(
            "INSERT INTO strain_compositions "
            "(strain_id, molecule_id, percentage, measurement_type, source) "
            "VALUES (?, ?, ?, 'lab_tested', ?)",
            (strain_id, molecule_id, round(median_val, 6),
             f"cannlytics_median_n{sample_count}"),
        )
        stats["compositions_created"] += 1
        enriched_strains.add(strain_id)

    stats["strains_enriched"] = len(enriched_strains)
    conn.commit()
    return stats
