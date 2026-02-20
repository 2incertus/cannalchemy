"""PubChem PUG REST API client for molecular data."""
import time
import httpx

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Pre-populated SMILES for known terpenes and cannabinoids
# Source: PubChem compound pages
KNOWN_COMPOUNDS = {
    # Terpenes
    "myrcene": {"smiles": "CC(=CCC/C(=C\\C)C)C", "cid": 31253, "mw": 136.23},
    "limonene": {"smiles": "CC1=CCC(CC1)C(=C)C", "cid": 22311, "mw": 136.23},
    "caryophyllene": {"smiles": "CC1=CCC(CC/C(=C\\CC1)C)(C)C=C", "cid": 5281515, "mw": 204.35},
    "linalool": {"smiles": "CC(=CCC/C(=C\\C)C)O", "cid": 6549, "mw": 154.25},
    "pinene": {"smiles": "CC1=CCC2CC1C2(C)C", "cid": 6654, "mw": 136.23},
    "humulene": {"smiles": "CC1=CCC(=CCC(=CCC=C1)C)C", "cid": 5281520, "mw": 204.35},
    "ocimene": {"smiles": "CC(=CCC=C(C)C=C)C", "cid": 5281553, "mw": 136.23},
    "terpinolene": {"smiles": "CC1=CCC(=C(C)C)CC1", "cid": 11463, "mw": 136.23},
    "bisabolol": {"smiles": "CC1=CCC(CC1)C(C)(CCC=C(C)C)O", "cid": 10586, "mw": 222.37},
    "valencene": {"smiles": "CC1=CCC2(CC1)C(CCC(=C2)C)C", "cid": 9855795, "mw": 204.35},
    "geraniol": {"smiles": "CC(=CCC/C(=C\\CO)C)C", "cid": 637566, "mw": 154.25},
    "camphene": {"smiles": "CC1(C2CCC(=C)C1C2)C", "cid": 6616, "mw": 136.23},
    "terpineol": {"smiles": "CC1=CCC(CC1)C(C)(C)O", "cid": 17100, "mw": 154.25},
    "phellandrene": {"smiles": "CC(C)C1CCC(=CC1)C", "cid": 7460, "mw": 136.23},
    "carene": {"smiles": "CC1=CCC2CC1C2(C)C", "cid": 26049, "mw": 136.23},
    "borneol": {"smiles": "CC1(C2CCC(C1(O)C2)C)C", "cid": 6552, "mw": 154.25},
    "sabinene": {"smiles": "CC(C)C12CCC(=C)C1C2", "cid": 18818, "mw": 136.23},
    "eucalyptol": {"smiles": "CC1(C2CCC(O1)(CC2)C)C", "cid": 2758, "mw": 154.25},
    "nerolidol": {"smiles": "CC(=CCC/C(=C\\CC/C(=C\\CO)C)C)C", "cid": 5284507, "mw": 222.37},
    "farnesene": {"smiles": "CC(=CCC/C(=C\\CC/C(=C\\C)C)C)C", "cid": 5281516, "mw": 204.35},
    "fenchol": {"smiles": "CC1(C2CCC(C1(O)C2)C)C", "cid": 14575, "mw": 154.25},
    "guaiol": {"smiles": "CC1CCC2(CC1C(=C)C)C(CCC2C(C)C)O", "cid": 227829, "mw": 222.37},
    # Cannabinoids
    "thc": {"smiles": "CCCCCC1=CC(=C2C3C=C(CCC3C(OC2=C1O)(C)C)C)O", "cid": 16078, "mw": 314.46},
    "cbd": {"smiles": "CCCCCC1=CC(=C(C(=C1)O)C2C=C(CCC2C(=C)C)C)O", "cid": 644019, "mw": 314.46},
    "cbn": {"smiles": "CCCCCC1=CC2=C(C3=C(C=CC(=C3)C)OC2(C)C)C(=C1)O", "cid": 2543, "mw": 310.43},
    "cbg": {"smiles": "CCCCCC1=CC(=C(C(=C1)O)CC=C(C)CCC=C(C)C)O", "cid": 5315659, "mw": 316.48},
    "cbc": {"smiles": "CCCCCC1=CC(=C(C2=C1OC(C2)(C)CCC=C(C)C)O)O", "cid": 30219, "mw": 314.46},
    "thcv": {"smiles": "CCCC1=CC(=C2C3C=C(CCC3C(OC2=C1O)(C)C)C)O", "cid": 62566, "mw": 286.41},
}


def lookup_compound(name: str) -> dict | None:
    """Look up a compound on PubChem by name.

    Returns dict with cid, molecular_weight, smiles, inchikey, logp, tpsa
    or None if not found.
    """
    try:
        url = f"{PUBCHEM_BASE}/compound/name/{name}/JSON"
        response = httpx.get(url, timeout=15.0)
        if response.status_code != 200:
            return None

        data = response.json()
        compound = data["PC_Compounds"][0]
        cid = compound["id"]["id"]["cid"]

        # Get properties
        time.sleep(0.3)  # Rate limiting
        props_url = (
            f"{PUBCHEM_BASE}/compound/cid/{cid}/property/"
            "MolecularWeight,IsomericSMILES,InChIKey,XLogP,TPSA/JSON"
        )
        props_resp = httpx.get(props_url, timeout=15.0)
        if props_resp.status_code != 200:
            return {"cid": cid}

        props = props_resp.json()["PropertyTable"]["Properties"][0]
        return {
            "cid": cid,
            "molecular_weight": props.get("MolecularWeight", 0),
            "smiles": props.get("IsomericSMILES", ""),
            "inchikey": props.get("InChIKey", ""),
            "logp": props.get("XLogP", None),
            "tpsa": props.get("TPSA", None),
        }
    except Exception:
        return None


def enrich_molecules_from_pubchem(conn, rate_limit_seconds: float = 0.5) -> dict:
    """Enrich molecules in the DB with PubChem data.

    First uses KNOWN_COMPOUNDS for instant lookups, then falls back to API
    for any molecules not in the known set.

    Returns stats dict.
    """
    stats = {"enriched_from_cache": 0, "enriched_from_api": 0, "failed": 0}

    rows = conn.execute(
        "SELECT id, name FROM molecules WHERE smiles = '' OR smiles IS NULL"
    ).fetchall()

    for mol_id, name in rows:
        name_lower = name.lower().strip()

        # Try known compounds first (no API call)
        if name_lower in KNOWN_COMPOUNDS:
            kc = KNOWN_COMPOUNDS[name_lower]
            conn.execute(
                "UPDATE molecules SET smiles=?, molecular_weight=?, pubchem_cid=? WHERE id=?",
                (kc["smiles"], kc["mw"], kc["cid"], mol_id),
            )
            stats["enriched_from_cache"] += 1
            continue

        # Fall back to PubChem API
        result = lookup_compound(name)
        if result:
            conn.execute(
                "UPDATE molecules SET smiles=?, molecular_weight=?, pubchem_cid=?, "
                "inchikey=?, logp=?, tpsa=? WHERE id=?",
                (
                    result.get("smiles", ""),
                    result.get("molecular_weight"),
                    result.get("cid"),
                    result.get("inchikey", ""),
                    result.get("logp"),
                    result.get("tpsa"),
                    mol_id,
                ),
            )
            stats["enriched_from_api"] += 1
        else:
            stats["failed"] += 1

        time.sleep(rate_limit_seconds)

    conn.commit()
    return stats
