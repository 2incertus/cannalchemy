"""Expand the molecule table with additional cannabinoids and seed binding affinities.

Adds CBN, CBG, CBC, THCV (with SMILES/MW/CID from KNOWN_COMPOUNDS cache)
and seeds all known binding affinities from KNOWN_BINDING_DATA.
"""
import sqlite3

from cannalchemy.data.pubchem import KNOWN_COMPOUNDS
from cannalchemy.data.chembl import KNOWN_RECEPTORS, KNOWN_BINDING_DATA

ADDITIONAL_CANNABINOIDS = ["cbn", "cbg", "cbc", "thcv"]


def expand_cannabinoids(conn: sqlite3.Connection) -> dict:
    """Insert missing cannabinoids, update SMILES, seed receptors and bindings.

    All operations use INSERT OR IGNORE for idempotency.

    Returns:
        dict with keys: molecules_added, smiles_updated, receptors_added, bindings_added
    """
    stats = {
        "molecules_added": 0,
        "smiles_updated": 0,
        "receptors_added": 0,
        "bindings_added": 0,
    }

    # --- (a) Insert missing cannabinoids with SMILES, MW, and CID ---
    all_cannabinoids = list(ADDITIONAL_CANNABINOIDS)
    # Also ensure THC and CBD exist (for completeness in empty-DB scenarios)
    for name in ["thc", "cbd"]:
        if name not in all_cannabinoids:
            all_cannabinoids.append(name)

    for name in all_cannabinoids:
        compound = KNOWN_COMPOUNDS.get(name, {})
        cur = conn.execute(
            "INSERT OR IGNORE INTO molecules "
            "(name, molecule_type, smiles, molecular_weight, pubchem_cid) "
            "VALUES (?, 'cannabinoid', ?, ?, ?)",
            (
                name,
                compound.get("smiles", ""),
                compound.get("mw"),
                compound.get("cid"),
            ),
        )
        if cur.rowcount == 1:
            stats["molecules_added"] += 1

    # --- (b) Update SMILES for existing cannabinoids that have empty SMILES ---
    rows = conn.execute(
        "SELECT id, name FROM molecules "
        "WHERE molecule_type = 'cannabinoid' AND (smiles = '' OR smiles IS NULL)"
    ).fetchall()
    for mol_id, mol_name in rows:
        compound = KNOWN_COMPOUNDS.get(mol_name.lower().strip())
        if compound:
            conn.execute(
                "UPDATE molecules SET smiles = ?, molecular_weight = ?, pubchem_cid = ? "
                "WHERE id = ?",
                (compound["smiles"], compound["mw"], compound["cid"], mol_id),
            )
            stats["smiles_updated"] += 1

    # --- (c) Ensure all receptors exist ---
    for rec_name, rec_data in KNOWN_RECEPTORS.items():
        cur = conn.execute(
            "INSERT OR IGNORE INTO receptors "
            "(name, uniprot_id, gene_name, location, function) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                rec_name,
                rec_data["uniprot_id"],
                rec_data["gene_name"],
                rec_data["location"],
                rec_data["function"],
            ),
        )
        if cur.rowcount == 1:
            stats["receptors_added"] += 1

    # --- (d) Seed all binding affinities ---
    # Build ID maps
    receptor_ids = {
        row[1]: row[0]
        for row in conn.execute("SELECT id, name FROM receptors").fetchall()
    }
    molecule_ids = {
        row[1]: row[0]
        for row in conn.execute("SELECT id, name FROM molecules").fetchall()
    }

    for binding in KNOWN_BINDING_DATA:
        mol_id = molecule_ids.get(binding["molecule"])
        rec_id = receptor_ids.get(binding["receptor"])
        if not mol_id or not rec_id:
            continue

        cur = conn.execute(
            "INSERT OR IGNORE INTO binding_affinities "
            "(molecule_id, receptor_id, ki_nm, ic50_nm, ec50_nm, action_type, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                mol_id,
                rec_id,
                binding.get("ki_nm"),
                binding.get("ic50_nm"),
                binding.get("ec50_nm"),
                binding.get("action_type", ""),
                binding.get("source", ""),
            ),
        )
        if cur.rowcount == 1:
            stats["bindings_added"] += 1

    conn.commit()
    return stats
