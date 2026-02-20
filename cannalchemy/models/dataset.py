"""Build feature/label matrices from the Cannalchemy DB for ML training.

Loads ML-ready strains (those with both chemical compositions and effect reports),
builds a feature matrix of terpene/cannabinoid percentages, and a multi-label
binary matrix for 51 canonical effects.

Usage:
    from cannalchemy.models.dataset import build_dataset
    X, y, meta = build_dataset("data/processed/cannalchemy.db")
"""
import logging
import sqlite3

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_molecules(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load molecule definitions ordered by type and name.

    Returns:
        DataFrame with columns: id, name, molecule_type.
    """
    return pd.read_sql_query(
        "SELECT id, name, molecule_type FROM molecules ORDER BY molecule_type, name",
        conn,
    )


def load_effects(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load effect definitions ordered by category and name.

    Returns:
        DataFrame with columns: id, name, category.
    """
    return pd.read_sql_query(
        "SELECT id, name, category FROM effects ORDER BY category, name",
        conn,
    )


def load_ml_strain_ids(conn: sqlite3.Connection) -> list[int]:
    """Get strain IDs that have both compositions and effect reports.

    Returns:
        Sorted list of strain IDs.
    """
    rows = conn.execute("""
        SELECT DISTINCT sc.strain_id
        FROM strain_compositions sc
        JOIN effect_reports er ON er.strain_id = sc.strain_id
        ORDER BY sc.strain_id
    """).fetchall()
    return [r[0] for r in rows]


def build_feature_matrix(
    conn: sqlite3.Connection,
    strain_ids: list[int],
    molecules: pd.DataFrame,
) -> pd.DataFrame:
    """Build feature matrix of chemical compositions.

    For strains with multiple composition entries per molecule (from different
    sources), values are averaged. Missing molecules are filled with 0.

    Args:
        conn: DB connection.
        strain_ids: List of strain IDs to include.
        molecules: DataFrame from load_molecules().

    Returns:
        DataFrame indexed by strain_id, columns are molecule names.
    """
    placeholders = ",".join("?" * len(strain_ids))
    df = pd.read_sql_query(
        f"""
        SELECT sc.strain_id, m.name AS molecule, AVG(sc.percentage) AS pct
        FROM strain_compositions sc
        JOIN molecules m ON m.id = sc.molecule_id
        WHERE sc.strain_id IN ({placeholders})
        GROUP BY sc.strain_id, m.name
        """,
        conn,
        params=strain_ids,
    )

    # Pivot to strain_id x molecule matrix
    feature_matrix = df.pivot(index="strain_id", columns="molecule", values="pct")

    # Ensure all molecule columns exist (even if no strain has that molecule)
    for mol_name in molecules["name"].values:
        if mol_name not in feature_matrix.columns:
            feature_matrix[mol_name] = 0.0

    # Reorder columns consistently
    col_order = sorted(feature_matrix.columns)
    feature_matrix = feature_matrix[col_order]

    # Fill NaN with 0 (strain doesn't have that molecule measured)
    feature_matrix = feature_matrix.fillna(0.0)

    return feature_matrix


def build_label_matrix(
    conn: sqlite3.Connection,
    strain_ids: list[int],
    effects: pd.DataFrame,
    min_report_count: int = 1,
) -> pd.DataFrame:
    """Build multi-label binary matrix of effects.

    An effect is considered present (1) for a strain if the total report count
    across all sources meets the minimum threshold.

    Args:
        conn: DB connection.
        strain_ids: List of strain IDs to include.
        effects: DataFrame from load_effects().
        min_report_count: Minimum total report count to mark effect as present.

    Returns:
        DataFrame indexed by strain_id, columns are effect names, values 0/1.
    """
    placeholders = ",".join("?" * len(strain_ids))
    df = pd.read_sql_query(
        f"""
        SELECT er.strain_id, e.name AS effect,
               SUM(er.report_count) AS total_reports
        FROM effect_reports er
        JOIN effects e ON e.id = er.effect_id
        WHERE er.strain_id IN ({placeholders})
        GROUP BY er.strain_id, e.name
        """,
        conn,
        params=strain_ids,
    )

    # Apply threshold
    df["present"] = (df["total_reports"] >= min_report_count).astype(int)

    # Pivot to strain_id x effect matrix
    label_matrix = df.pivot(index="strain_id", columns="effect", values="present")

    # Ensure all effect columns exist
    for eff_name in effects["name"].values:
        if eff_name not in label_matrix.columns:
            label_matrix[eff_name] = 0

    # Reorder columns consistently
    col_order = sorted(label_matrix.columns)
    label_matrix = label_matrix[col_order]

    # Fill NaN with 0 (strain has no report for that effect)
    label_matrix = label_matrix.fillna(0).astype(int)

    return label_matrix


TERPENE_NAMES = [
    "bisabolol", "borneol", "camphene", "carene", "caryophyllene",
    "eucalyptol", "farnesene", "fenchol", "geraniol", "guaiol",
    "humulene", "limonene", "linalool", "myrcene", "nerolidol",
    "ocimene", "phellandrene", "pinene", "terpineol", "terpinolene",
    "valencene",
]
CANNABINOID_NAMES = ["cbc", "cbd", "cbg", "cbn", "thc", "thcv"]


def add_engineered_features(
    X: pd.DataFrame,
    strain_info: pd.DataFrame,
) -> pd.DataFrame:
    """Add engineered features to the chemical feature matrix.

    Adds:
        - strain_type one-hot (is_indica, is_sativa, is_hybrid)
        - total_terpenes, total_cannabinoids
        - terpene_diversity (count of non-zero terpenes)
        - thc_cbd_ratio
        - dominant_terpene_pct (max terpene value)

    Args:
        X: Base feature matrix (molecule columns).
        strain_info: DataFrame with strain_type column, indexed by strain_id.

    Returns:
        Extended feature matrix with engineered columns appended.
    """
    X_eng = X.copy()

    # Strain type one-hot encoding
    for st in ("indica", "sativa", "hybrid"):
        col = f"is_{st}"
        X_eng[col] = (strain_info.reindex(X.index)["strain_type"] == st).astype(float)

    # Terpene aggregates
    terp_cols = [c for c in X.columns if c in TERPENE_NAMES]
    cann_cols = [c for c in X.columns if c in CANNABINOID_NAMES]

    if terp_cols:
        X_eng["total_terpenes"] = X[terp_cols].sum(axis=1)
        X_eng["terpene_diversity"] = (X[terp_cols] > 0).sum(axis=1).astype(float)
        X_eng["dominant_terpene_pct"] = X[terp_cols].max(axis=1)

    if cann_cols:
        X_eng["total_cannabinoids"] = X[cann_cols].sum(axis=1)

    # THC/CBD ratio (handle CBD=0 gracefully)
    if "thc" in X.columns and "cbd" in X.columns:
        cbd_safe = X["cbd"].replace(0, 0.01)
        X_eng["thc_cbd_ratio"] = X["thc"] / cbd_safe

    return X_eng


def build_dataset(
    db_path: str,
    min_report_count: int = 1,
    min_positive_strains: int = 30,
    engineer_features: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Build complete ML dataset from Cannalchemy DB.

    Args:
        db_path: Path to Cannalchemy SQLite database.
        min_report_count: Minimum report count to consider an effect present.
        min_positive_strains: Drop effect columns with fewer positive strains
            than this threshold (too rare to learn reliably).
        engineer_features: Add engineered features (strain type, ratios, etc.).

    Returns:
        Tuple of (X, y, metadata):
            X: Feature matrix (strain_id x molecule), float values.
            y: Label matrix (strain_id x effect), binary 0/1.
            metadata: Dict with dataset statistics and column info.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    molecules = load_molecules(conn)
    effects = load_effects(conn)
    strain_ids = load_ml_strain_ids(conn)

    logger.info("Building dataset: %d ML-ready strains", len(strain_ids))

    # Build matrices
    X = build_feature_matrix(conn, strain_ids, molecules)
    y = build_label_matrix(conn, strain_ids, effects, min_report_count)

    # Align indices (both should have same strain_ids)
    common_ids = X.index.intersection(y.index)
    X = X.loc[common_ids]
    y = y.loc[common_ids]

    # Load strain metadata
    placeholders = ",".join("?" * len(common_ids))
    strain_info = pd.read_sql_query(
        f"SELECT id, name, strain_type FROM strains WHERE id IN ({placeholders})",
        conn,
        params=list(common_ids),
    )
    strain_info = strain_info.set_index("id")

    conn.close()

    # Optionally add engineered features
    if engineer_features:
        X = add_engineered_features(X, strain_info)
        logger.info("Added engineered features: %d total columns", X.shape[1])

    # Filter out rare effects
    effect_counts = y.sum()
    kept_effects = effect_counts[effect_counts >= min_positive_strains].index.tolist()
    dropped_effects = effect_counts[effect_counts < min_positive_strains].index.tolist()
    y = y[kept_effects]

    logger.info(
        "Features: %d columns | Labels: %d effects (dropped %d rare)",
        X.shape[1], y.shape[1], len(dropped_effects),
    )

    metadata = {
        "n_strains": len(common_ids),
        "n_features": X.shape[1],
        "n_effects": y.shape[1],
        "n_effects_dropped": len(dropped_effects),
        "dropped_effects": dropped_effects,
        "feature_names": list(X.columns),
        "effect_names": list(y.columns),
        "effect_positive_counts": effect_counts[kept_effects].to_dict(),
        "strain_types": strain_info["strain_type"].value_counts().to_dict(),
        "feature_fill_rate": float((X > 0).mean().mean()),
        "label_density": float(y.mean().mean()),
        "engineered": engineer_features,
    }

    logger.info(
        "Dataset ready: %d strains x %d features → %d effects (fill=%.1f%%, density=%.1f%%)",
        metadata["n_strains"], metadata["n_features"], metadata["n_effects"],
        metadata["feature_fill_rate"] * 100, metadata["label_density"] * 100,
    )

    return X, y, metadata
