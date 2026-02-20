"""Strain name deduplication using fuzzy string matching.

Uses union-find clustering with rapidfuzz to group similar normalized
strain names, then merges duplicates by keeping the "richest" strain
(most composition data + effect reports) as canonical.
"""
import sqlite3
from rapidfuzz import fuzz, process


def _find_root(parent: dict[str, str], name: str) -> str:
    """Find root of union-find tree with path compression."""
    while parent[name] != name:
        parent[name] = parent[parent[name]]
        name = parent[name]
    return name


def _union(parent: dict[str, str], rank: dict[str, int], a: str, b: str) -> None:
    """Union two sets by rank."""
    ra, rb = _find_root(parent, a), _find_root(parent, b)
    if ra == rb:
        return
    if rank[ra] < rank[rb]:
        ra, rb = rb, ra
    parent[rb] = ra
    if rank[ra] == rank[rb]:
        rank[ra] += 1


def find_duplicate_clusters(
    conn: sqlite3.Connection,
    threshold: int = 90,
    limit_per_query: int = 3,
) -> list[list[str]]:
    """Find clusters of duplicate strain names using fuzzy matching.

    Uses union-find algorithm with rapidfuzz to group similar normalized
    strain names. Compares each name against all others using
    process.extract with fuzz.ratio scorer.

    Args:
        conn: SQLite database connection.
        threshold: Minimum similarity score (0-100) to consider a match.
        limit_per_query: Max number of matches to return per name from
            process.extract.

    Returns:
        List of clusters, where each cluster is a list of normalized_names
        with 2 or more members.
    """
    rows = conn.execute(
        "SELECT DISTINCT normalized_name FROM strains ORDER BY normalized_name"
    ).fetchall()
    names = [r[0] for r in rows]

    if len(names) < 2:
        return []

    # Initialize union-find
    parent = {n: n for n in names}
    rank = {n: 0 for n in names}

    # Compare each name against all others
    for i, name in enumerate(names):
        # Build choices from remaining names to avoid self-match
        choices = names[i + 1 :]
        if not choices:
            continue

        matches = process.extract(
            name,
            choices,
            scorer=fuzz.ratio,
            score_cutoff=threshold,
            limit=limit_per_query,
        )

        for match_name, score, _idx in matches:
            _union(parent, rank, name, match_name)

    # Collect clusters
    clusters: dict[str, list[str]] = {}
    for name in names:
        root = _find_root(parent, name)
        clusters.setdefault(root, []).append(name)

    # Return only clusters with 2+ members
    return [c for c in clusters.values() if len(c) >= 2]


def merge_strain_cluster(
    conn: sqlite3.Connection,
    cluster: list[str],
) -> str:
    """Merge a cluster of duplicate strain names.

    Picks the "richest" strain (most strain_compositions + effect_reports)
    as canonical, then creates strain_aliases entries for all others
    pointing to the canonical strain.

    Uses INSERT OR IGNORE for idempotency.

    Args:
        conn: SQLite database connection.
        cluster: List of normalized_names to merge.

    Returns:
        The canonical normalized_name chosen as the merge target.
    """
    if len(cluster) < 2:
        return cluster[0] if cluster else ""

    # Get all strains in this cluster with their data richness
    placeholders = ",".join("?" * len(cluster))
    rows = conn.execute(
        f"""
        SELECT s.id, s.normalized_name,
            COALESCE(comp.cnt, 0) + COALESCE(eff.cnt, 0) AS richness
        FROM strains s
        LEFT JOIN (
            SELECT strain_id, COUNT(*) AS cnt
            FROM strain_compositions
            GROUP BY strain_id
        ) comp ON comp.strain_id = s.id
        LEFT JOIN (
            SELECT strain_id, COUNT(*) AS cnt
            FROM effect_reports
            GROUP BY strain_id
        ) eff ON eff.strain_id = s.id
        WHERE s.normalized_name IN ({placeholders})
        ORDER BY richness DESC, s.id ASC
        """,
        cluster,
    ).fetchall()

    if not rows:
        return ""

    # The richest strain becomes canonical
    canonical_id = rows[0][0]
    canonical_name = rows[0][1]

    # Create aliases for all non-canonical strains
    for strain_id, norm_name, _richness in rows:
        if strain_id == canonical_id:
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO strain_aliases
                (alias_strain_id, canonical_strain_id, match_score)
            VALUES (?, ?, ?)
            """,
            (strain_id, canonical_id, 100.0),
        )

    conn.commit()
    return canonical_name


def run_deduplication(
    conn: sqlite3.Connection,
    threshold: int = 90,
) -> dict:
    """Orchestrate full deduplication: find clusters, merge each.

    Args:
        conn: SQLite database connection.
        threshold: Minimum similarity score for clustering.

    Returns:
        Stats dict with clusters_found and aliases_created.
    """
    clusters = find_duplicate_clusters(conn, threshold=threshold)

    aliases_before = conn.execute("SELECT COUNT(*) FROM strain_aliases").fetchone()[0]

    for cluster in clusters:
        merge_strain_cluster(conn, cluster)

    aliases_after = conn.execute("SELECT COUNT(*) FROM strain_aliases").fetchone()[0]

    return {
        "clusters_found": len(clusters),
        "aliases_created": aliases_after - aliases_before,
    }
