"""Database schema definition and initialization."""
import sqlite3
from pathlib import Path

DB_TABLES = [
    "molecules",
    "receptors",
    "binding_affinities",
    "strains",
    "strain_compositions",
    "effects",
    "effect_reports",
    "lab_results",
    "data_sources",
]

SCHEMA_SQL = """
-- Molecules: terpenes, cannabinoids, flavonoids
CREATE TABLE IF NOT EXISTS molecules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    smiles TEXT DEFAULT '',
    molecular_weight REAL,
    logp REAL,
    tpsa REAL,
    molecule_type TEXT CHECK(molecule_type IN ('terpene', 'cannabinoid', 'flavonoid', 'other')) DEFAULT 'other',
    pubchem_cid INTEGER,
    inchikey TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Receptors: CB1, CB2, TRPV1, 5-HT, etc.
CREATE TABLE IF NOT EXISTS receptors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    uniprot_id TEXT DEFAULT '',
    gene_name TEXT DEFAULT '',
    location TEXT DEFAULT '',
    function TEXT DEFAULT '',
    description TEXT DEFAULT ''
);

-- Binding affinities: molecule <-> receptor interactions
CREATE TABLE IF NOT EXISTS binding_affinities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    molecule_id INTEGER NOT NULL REFERENCES molecules(id),
    receptor_id INTEGER NOT NULL REFERENCES receptors(id),
    ki_nm REAL,
    ic50_nm REAL,
    ec50_nm REAL,
    action_type TEXT DEFAULT '',
    source TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    UNIQUE(molecule_id, receptor_id, source)
);

-- Strains imported from various sources
CREATE TABLE IF NOT EXISTS strains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    strain_type TEXT CHECK(strain_type IN ('indica', 'sativa', 'hybrid', 'unknown')) DEFAULT 'unknown',
    description TEXT DEFAULT '',
    image_url TEXT DEFAULT '',
    source TEXT DEFAULT '',
    source_id TEXT DEFAULT '',
    UNIQUE(normalized_name, source)
);

-- Strain chemical compositions (terpene/cannabinoid percentages)
CREATE TABLE IF NOT EXISTS strain_compositions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strain_id INTEGER NOT NULL REFERENCES strains(id),
    molecule_id INTEGER NOT NULL REFERENCES molecules(id),
    percentage REAL NOT NULL,
    measurement_type TEXT CHECK(measurement_type IN ('lab_tested', 'reported', 'estimated')) DEFAULT 'reported',
    source TEXT DEFAULT '',
    UNIQUE(strain_id, molecule_id, source)
);

-- Effects taxonomy
CREATE TABLE IF NOT EXISTS effects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT CHECK(category IN ('positive', 'negative', 'medical', 'other')) DEFAULT 'other',
    description TEXT DEFAULT ''
);

-- Effect reports: how many users report an effect for a strain
CREATE TABLE IF NOT EXISTS effect_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strain_id INTEGER NOT NULL REFERENCES strains(id),
    effect_id INTEGER NOT NULL REFERENCES effects(id),
    report_count INTEGER DEFAULT 0,
    source TEXT DEFAULT '',
    UNIQUE(strain_id, effect_id, source)
);

-- Lab test results (higher fidelity than strain_compositions)
CREATE TABLE IF NOT EXISTS lab_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strain_name TEXT NOT NULL,
    normalized_strain_name TEXT NOT NULL,
    lab_name TEXT DEFAULT '',
    state TEXT DEFAULT '',
    test_date TEXT DEFAULT '',
    molecule_name TEXT NOT NULL,
    concentration REAL NOT NULL,
    unit TEXT DEFAULT 'percent',
    source_file TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Data source provenance tracking
CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    source_type TEXT DEFAULT '',
    url TEXT DEFAULT '',
    last_updated DATETIME,
    record_count INTEGER DEFAULT 0,
    notes TEXT DEFAULT ''
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_strain_compositions_strain ON strain_compositions(strain_id);
CREATE INDEX IF NOT EXISTS idx_strain_compositions_molecule ON strain_compositions(molecule_id);
CREATE INDEX IF NOT EXISTS idx_binding_affinities_molecule ON binding_affinities(molecule_id);
CREATE INDEX IF NOT EXISTS idx_binding_affinities_receptor ON binding_affinities(receptor_id);
CREATE INDEX IF NOT EXISTS idx_effect_reports_strain ON effect_reports(strain_id);
CREATE INDEX IF NOT EXISTS idx_effect_reports_effect ON effect_reports(effect_id);
CREATE INDEX IF NOT EXISTS idx_lab_results_strain ON lab_results(normalized_strain_name);
CREATE INDEX IF NOT EXISTS idx_strains_normalized ON strains(normalized_name);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize the database with the schema. Idempotent."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
