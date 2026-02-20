"""Data pipeline: orchestrates import, enrichment, and graph building."""
from dataclasses import dataclass
from pathlib import Path

from cannalchemy.data.schema import init_db
from cannalchemy.data.strain_import import import_from_strain_tracker
from cannalchemy.data.pubchem import enrich_molecules_from_pubchem, KNOWN_COMPOUNDS
from cannalchemy.data.chembl import seed_receptors_and_bindings
from cannalchemy.data.graph import build_knowledge_graph


@dataclass
class PipelineConfig:
    db_path: str = "data/processed/cannalchemy.db"
    strain_tracker_db: str | None = "/srv/appdata/strain-tracker/strain-tracker.db"
    skip_pubchem_api: bool = False
    skip_chembl_api: bool = False


def run_pipeline(config: PipelineConfig) -> dict:
    """Run the full data pipeline.

    Steps:
    1. Initialize database schema
    2. Import strain-tracker data (if available)
    3. Seed receptor and binding data from known literature
    4. Enrich molecules with PubChem data (SMILES, MW, etc.)
    5. Build knowledge graph

    Returns combined stats dict.
    """
    stats = {}

    # 1. Initialize DB
    conn = init_db(config.db_path)

    # 2. Import from strain-tracker
    if config.strain_tracker_db and Path(config.strain_tracker_db).exists():
        import_stats = import_from_strain_tracker(conn, config.strain_tracker_db)
        stats.update(import_stats)
    else:
        stats["strains_imported"] = 0
        # Seed molecules from known compounds even without strain-tracker
        for name, data in KNOWN_COMPOUNDS.items():
            mol_type = "cannabinoid" if name in ("thc", "cbd", "cbn", "cbg", "cbc", "thcv") else "terpene"
            conn.execute(
                "INSERT OR IGNORE INTO molecules (name, molecule_type, smiles, molecular_weight, pubchem_cid) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, mol_type, data["smiles"], data["mw"], data["cid"]),
            )
        conn.commit()

    # 3. Seed receptors and binding data
    chembl_stats = seed_receptors_and_bindings(conn)
    stats.update(chembl_stats)

    # 4. Enrich molecules from PubChem
    if not config.skip_pubchem_api:
        pubchem_stats = enrich_molecules_from_pubchem(conn)
        stats.update(pubchem_stats)
    else:
        # Still apply known compound data without API calls
        for name, data in KNOWN_COMPOUNDS.items():
            conn.execute(
                "UPDATE molecules SET smiles=?, molecular_weight=?, pubchem_cid=? "
                "WHERE name=? AND (smiles='' OR smiles IS NULL)",
                (data["smiles"], data["mw"], data["cid"], name),
            )
        conn.commit()
        stats["enriched_from_cache"] = len(KNOWN_COMPOUNDS)

    # 5. Build knowledge graph
    graph = build_knowledge_graph(conn)
    stats["graph_nodes"] = graph.number_of_nodes()
    stats["graph_edges"] = graph.number_of_edges()

    conn.close()
    return stats


def main():
    """CLI entry point."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Cannalchemy data pipeline")
    parser.add_argument("--db-path", default="data/processed/cannalchemy.db")
    parser.add_argument("--strain-tracker-db", default="/srv/appdata/strain-tracker/strain-tracker.db")
    parser.add_argument("--skip-pubchem", action="store_true")
    parser.add_argument("--skip-chembl", action="store_true")
    args = parser.parse_args()

    config = PipelineConfig(
        db_path=args.db_path,
        strain_tracker_db=args.strain_tracker_db,
        skip_pubchem_api=args.skip_pubchem,
        skip_chembl_api=args.skip_chembl,
    )

    print("Running Cannalchemy data pipeline...")
    stats = run_pipeline(config)
    print(json.dumps(stats, indent=2))
    print("Done.")
