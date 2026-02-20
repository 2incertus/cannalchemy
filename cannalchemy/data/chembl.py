"""ChEMBL API client for receptor binding affinity data."""
import httpx

CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"

# Known cannabinoid receptors and related targets
KNOWN_RECEPTORS = {
    "CB1": {
        "chembl_id": "CHEMBL218",
        "uniprot_id": "P21554",
        "gene_name": "CNR1",
        "location": "brain, central nervous system",
        "function": "Primary psychoactive cannabinoid receptor. Mediates euphoria, appetite, pain modulation, memory.",
    },
    "CB2": {
        "chembl_id": "CHEMBL253",
        "uniprot_id": "P34972",
        "gene_name": "CNR2",
        "location": "immune system, peripheral tissues",
        "function": "Anti-inflammatory, immunomodulatory. Key role in pain and inflammation without psychoactive effects.",
    },
    "TRPV1": {
        "chembl_id": "CHEMBL4794",
        "uniprot_id": "Q8NER1",
        "gene_name": "TRPV1",
        "location": "sensory neurons",
        "function": "Vanilloid receptor. Mediates pain sensation, thermoregulation. Activated by capsaicin and some cannabinoids.",
    },
    "5-HT1A": {
        "chembl_id": "CHEMBL214",
        "uniprot_id": "P08908",
        "gene_name": "HTR1A",
        "location": "brain (raphe nuclei, hippocampus)",
        "function": "Serotonin receptor. Mediates anxiety reduction, mood regulation, anti-depressant effects.",
    },
    "PPARgamma": {
        "chembl_id": "CHEMBL235",
        "uniprot_id": "P37231",
        "gene_name": "PPARG",
        "location": "adipose tissue, immune cells",
        "function": "Nuclear receptor. Anti-inflammatory, neuroprotective. CBD is a partial agonist.",
    },
    "GPR55": {
        "chembl_id": "CHEMBL3802",
        "uniprot_id": "Q9Y2T6",
        "gene_name": "GPR55",
        "location": "brain, GI tract, bones",
        "function": "Putative cannabinoid receptor. Involved in bone density, anxiety, neuroprotection.",
    },
}

# Pre-populated binding data from literature
# Sources: various pharmacology papers, ChEMBL bioactivity data
# Ki values in nanomolar (nM). Lower Ki = stronger binding.
KNOWN_BINDING_DATA = [
    # THC bindings
    {"molecule": "thc", "receptor": "CB1", "ki_nm": 40.7, "action_type": "partial agonist", "source": "Pertwee 2008"},
    {"molecule": "thc", "receptor": "CB2", "ki_nm": 36.4, "action_type": "partial agonist", "source": "Pertwee 2008"},
    {"molecule": "thc", "receptor": "TRPV1", "ki_nm": 1500.0, "action_type": "agonist", "source": "De Petrocellis 2011"},
    {"molecule": "thc", "receptor": "GPR55", "ki_nm": 8.0, "action_type": "agonist", "source": "Ryberg 2007"},
    # CBD bindings
    {"molecule": "cbd", "receptor": "CB1", "ki_nm": 4900.0, "action_type": "negative allosteric modulator", "source": "Laprairie 2015"},
    {"molecule": "cbd", "receptor": "CB2", "ki_nm": 2860.0, "action_type": "inverse agonist", "source": "Thomas 2007"},
    {"molecule": "cbd", "receptor": "5-HT1A", "ki_nm": 16.0, "action_type": "agonist", "source": "Russo 2011"},
    {"molecule": "cbd", "receptor": "TRPV1", "ki_nm": 1000.0, "action_type": "agonist", "source": "Bisogno 2001"},
    {"molecule": "cbd", "receptor": "PPARgamma", "ec50_nm": 5000.0, "action_type": "partial agonist", "source": "O'Sullivan 2009"},
    {"molecule": "cbd", "receptor": "GPR55", "ki_nm": 445.0, "action_type": "antagonist", "source": "Ryberg 2007"},
    # CBN
    {"molecule": "cbn", "receptor": "CB1", "ki_nm": 211.2, "action_type": "partial agonist", "source": "Mahadevan 2000"},
    {"molecule": "cbn", "receptor": "CB2", "ki_nm": 126.4, "action_type": "partial agonist", "source": "Mahadevan 2000"},
    # CBG
    {"molecule": "cbg", "receptor": "CB1", "ki_nm": 897.0, "action_type": "partial agonist", "source": "Cascio 2010"},
    {"molecule": "cbg", "receptor": "CB2", "ki_nm": 153.0, "action_type": "partial agonist", "source": "Cascio 2010"},
    {"molecule": "cbg", "receptor": "5-HT1A", "ki_nm": 51.9, "action_type": "antagonist", "source": "Cascio 2010"},
    # Terpene interactions (less studied, but documented)
    {"molecule": "caryophyllene", "receptor": "CB2", "ki_nm": 155.0, "action_type": "full agonist", "source": "Gertsch 2008"},
    {"molecule": "myrcene", "receptor": "TRPV1", "ki_nm": 8700.0, "action_type": "modulator", "source": "Surendran 2021"},
    {"molecule": "linalool", "receptor": "5-HT1A", "ki_nm": 12000.0, "action_type": "modulator", "source": "Guzmán-Gutiérrez 2015"},
    {"molecule": "limonene", "receptor": "5-HT1A", "ki_nm": 15000.0, "action_type": "modulator", "source": "Zhou 2009"},
]


def fetch_binding_data(
    target_chembl_id: str,
    limit: int = 100,
) -> list[dict]:
    """Fetch binding affinity data from ChEMBL for a given target.

    Returns list of dicts with molecule_chembl_id, pchembl_value,
    standard_type, standard_value, etc.
    """
    url = (
        f"{CHEMBL_BASE}/activity.json"
        f"?target_chembl_id={target_chembl_id}"
        f"&standard_type__in=Ki,IC50,EC50"
        f"&limit={limit}"
        f"&offset=0"
    )
    try:
        resp = httpx.get(url, timeout=30.0)
        if resp.status_code != 200:
            return []
        data = resp.json()
        activities = data.get("activities", [])
        return [
            {
                "molecule_chembl_id": a.get("molecule_chembl_id"),
                "molecule_name": (a.get("molecule_pref_name") or "").lower(),
                "standard_type": a.get("standard_type"),
                "standard_value": float(a["standard_value"]) if a.get("standard_value") else None,
                "standard_units": a.get("standard_units"),
                "pchembl_value": float(a["pchembl_value"]) if a.get("pchembl_value") else None,
                "assay_type": a.get("assay_type"),
                "source": "ChEMBL",
            }
            for a in activities
            if a.get("standard_value")
        ]
    except Exception:
        return []


def seed_receptors_and_bindings(conn) -> dict:
    """Seed the database with known receptor and binding data.

    Returns stats dict.
    """
    stats = {"receptors_created": 0, "bindings_created": 0}

    # Insert receptors
    for name, data in KNOWN_RECEPTORS.items():
        conn.execute(
            "INSERT OR IGNORE INTO receptors "
            "(name, uniprot_id, gene_name, location, function) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, data["uniprot_id"], data["gene_name"],
             data["location"], data["function"]),
        )
        stats["receptors_created"] += 1

    # Build ID maps
    receptor_ids = {}
    for row in conn.execute("SELECT id, name FROM receptors").fetchall():
        receptor_ids[row[1]] = row[0]

    molecule_ids = {}
    for row in conn.execute("SELECT id, name FROM molecules").fetchall():
        molecule_ids[row[1]] = row[0]

    # Insert binding affinities
    for binding in KNOWN_BINDING_DATA:
        mol_id = molecule_ids.get(binding["molecule"])
        rec_id = receptor_ids.get(binding["receptor"])
        if not mol_id or not rec_id:
            continue

        conn.execute(
            "INSERT OR IGNORE INTO binding_affinities "
            "(molecule_id, receptor_id, ki_nm, ic50_nm, ec50_nm, action_type, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                mol_id, rec_id,
                binding.get("ki_nm"),
                binding.get("ic50_nm"),
                binding.get("ec50_nm"),
                binding.get("action_type", ""),
                binding.get("source", ""),
            ),
        )
        stats["bindings_created"] += 1

    conn.commit()
    return stats
