# Cannalchemy Phase 1: Data Foundation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the data pipeline, SQLite schema, molecular knowledge graph, and exploratory notebooks for the Cannalchemy terpene/cannabinoid effect prediction system.

**Architecture:** Python package at `~/cannalchemy/` (git worktree on `cannalchemy` branch). SQLite for persistent storage, NetworkX for in-memory knowledge graph. Data ingested from Strain Tracker DB, PubChem, ChEMBL, and public cannabis datasets.

**Tech Stack:** Python 3.11+, SQLite, NetworkX, RDKit, httpx, pandas, rapidfuzz, Jupyter, pytest

**Design doc:** `docs/plans/2026-02-20-cannalchemy-design.md`

---

## Task 1: Project Scaffold

**Files:**
- Create: `~/cannalchemy/pyproject.toml`
- Create: `~/cannalchemy/cannalchemy/__init__.py`
- Create: `~/cannalchemy/cannalchemy/data/__init__.py`
- Create: `~/cannalchemy/cannalchemy/molecules/__init__.py`
- Create: `~/cannalchemy/cannalchemy/models/__init__.py`
- Create: `~/cannalchemy/cannalchemy/api/__init__.py`
- Create: `~/cannalchemy/cannalchemy/explain/__init__.py`
- Create: `~/cannalchemy/tests/__init__.py`
- Create: `~/cannalchemy/README.md`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cannalchemy"
version = "0.1.0"
description = "AI-powered terpene/cannabinoid effect prediction grounded in molecular pharmacology"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
    "networkx>=3.0",
    "httpx>=0.27",
    "pandas>=2.0",
    "rapidfuzz>=3.0",
    "sqlalchemy>=2.0",
]

[project.optional-dependencies]
chemistry = ["rdkit"]
ml = ["scikit-learn>=1.4", "xgboost>=2.0"]
api = ["fastapi>=0.115", "uvicorn>=0.30"]
notebooks = ["jupyter", "matplotlib", "seaborn"]
dev = ["pytest>=8.0", "pytest-cov"]
all = ["cannalchemy[chemistry,ml,api,notebooks,dev]"]
```

**Step 2: Create package __init__.py files**

All `__init__.py` files are empty except the root:

```python
# cannalchemy/__init__.py
"""Cannalchemy: AI-powered terpene/cannabinoid effect prediction."""
__version__ = "0.1.0"
```

**Step 3: Create minimal README.md**

```markdown
# Cannalchemy

AI-powered cannabis effect prediction grounded in molecular pharmacology.

Predicts effects from terpene/cannabinoid chemistry (and vice versa) using
ensemble ML models, molecular fingerprints, and receptor binding data.

## Quick Start

```bash
pip install -e ".[all]"
```

## Status

Phase 1: Data Foundation (in progress)
```

**Step 4: Create directory structure**

```bash
cd ~/cannalchemy
mkdir -p cannalchemy/{data,molecules,models,api,explain}
mkdir -p tests
mkdir -p notebooks
mkdir -p data/{raw,processed,models}
```

**Step 5: Install in dev mode**

Run: `cd ~/cannalchemy && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`

Expected: Package installs without errors.

**Step 6: Verify import works**

Run: `cd ~/cannalchemy && .venv/bin/python -c "import cannalchemy; print(cannalchemy.__version__)"`

Expected: `0.1.0`

**Step 7: Commit**

```bash
cd ~/cannalchemy
git add -A
git commit -m "feat: scaffold cannalchemy package structure"
```

---

## Task 2: SQLite Schema

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/schema.py`
- Create: `~/cannalchemy/tests/test_schema.py`

**Step 1: Write the failing test**

```python
# tests/test_schema.py
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db, DB_TABLES

def test_init_db_creates_all_tables():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cur.fetchall()}
        conn.close()
        for table in DB_TABLES:
            assert table in tables, f"Missing table: {table}"

def test_molecules_table_has_correct_columns():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(molecules)")
        columns = {row[1] for row in cur.fetchall()}
        conn.close()
        expected = {"id", "name", "smiles", "molecular_weight", "logp",
                    "tpsa", "molecule_type", "pubchem_cid", "inchikey"}
        assert expected.issubset(columns)

def test_init_db_is_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        init_db(db_path)
        init_db(db_path)  # Should not raise
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        count = cur.fetchone()[0]
        conn.close()
        assert count > 0
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_schema.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'cannalchemy.data.schema'`

**Step 3: Write the schema module**

```python
# cannalchemy/data/schema.py
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
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_schema.py -v`

Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/schema.py tests/test_schema.py
git commit -m "feat: add SQLite schema with molecules, receptors, strains, effects tables"
```

---

## Task 3: Strain Name Normalization

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/normalize.py`
- Create: `~/cannalchemy/tests/test_normalize.py`

**Step 1: Write the failing test**

```python
# tests/test_normalize.py
from cannalchemy.data.normalize import normalize_strain_name, match_strain_names

def test_normalize_basic():
    assert normalize_strain_name("Blue Dream") == "blue dream"

def test_normalize_strips_whitespace():
    assert normalize_strain_name("  Blue  Dream  ") == "blue dream"

def test_normalize_removes_special_chars():
    assert normalize_strain_name("Blue Dream #3") == "blue dream 3"

def test_normalize_handles_common_variants():
    # These should all normalize to the same thing
    names = ["OG Kush", "O.G. Kush", "OG-Kush", "og kush"]
    normalized = {normalize_strain_name(n) for n in names}
    assert len(normalized) == 1

def test_match_strain_names_exact():
    known = ["blue dream", "og kush", "sour diesel"]
    result = match_strain_names("Blue Dream", known)
    assert result[0][0] == "blue dream"
    assert result[0][1] >= 95  # confidence score

def test_match_strain_names_fuzzy():
    known = ["blue dream", "og kush", "sour diesel"]
    result = match_strain_names("Blu Dream", known)
    assert result[0][0] == "blue dream"
    assert result[0][1] >= 80
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_normalize.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the normalization module**

```python
# cannalchemy/data/normalize.py
"""Strain name normalization and fuzzy matching."""
import re
from rapidfuzz import fuzz, process


def normalize_strain_name(name: str) -> str:
    """Normalize a strain name for deduplication.

    Lowercases, strips whitespace, removes punctuation except spaces,
    collapses multiple spaces.
    """
    name = name.lower().strip()
    # Remove periods, hyphens, underscores, hash symbols
    name = re.sub(r'[.\-_#\'\"()]', ' ', name)
    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def match_strain_names(
    query: str,
    known_names: list[str],
    limit: int = 5,
    score_cutoff: float = 70.0,
) -> list[tuple[str, float]]:
    """Find the best matches for a strain name in a list of known names.

    Returns list of (name, score) tuples, sorted by score descending.
    Score is 0-100 where 100 is exact match.
    """
    normalized_query = normalize_strain_name(query)
    results = process.extract(
        normalized_query,
        known_names,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=score_cutoff,
    )
    return [(match, score) for match, score, _ in results]
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_normalize.py -v`

Expected: All 6 tests PASS.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/normalize.py tests/test_normalize.py
git commit -m "feat: add strain name normalization and fuzzy matching"
```

---

## Task 4: Strain Tracker Import

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/strain_import.py`
- Create: `~/cannalchemy/tests/test_strain_import.py`

**Step 1: Write the failing test**

```python
# tests/test_strain_import.py
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.strain_import import import_from_strain_tracker

# Path to the real strain-tracker DB
STRAIN_TRACKER_DB = "/srv/appdata/strain-tracker/strain-tracker.db"

def test_import_creates_strains():
    """Test that import populates strains table from strain-tracker."""
    if not os.path.exists(STRAIN_TRACKER_DB):
        import pytest
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        stats = import_from_strain_tracker(conn, STRAIN_TRACKER_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM strains")
        count = cur.fetchone()[0]
        conn.close()
        assert count > 20000  # We know there are 25K+
        assert stats["strains_imported"] > 20000

def test_import_creates_molecules():
    """Test that terpenes are imported as molecules."""
    if not os.path.exists(STRAIN_TRACKER_DB):
        import pytest
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        import_from_strain_tracker(conn, STRAIN_TRACKER_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM molecules WHERE molecule_type='terpene'")
        count = cur.fetchone()[0]
        conn.close()
        assert count >= 18  # 20 terpenes minus 'null' and other junk

def test_import_creates_strain_compositions():
    """Test that terpene percentages are linked to strains."""
    if not os.path.exists(STRAIN_TRACKER_DB):
        import pytest
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        import_from_strain_tracker(conn, STRAIN_TRACKER_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM strain_compositions")
        count = cur.fetchone()[0]
        conn.close()
        assert count > 50000  # 68K terpene rows minus junk

def test_import_creates_effects():
    """Test that effects are imported."""
    if not os.path.exists(STRAIN_TRACKER_DB):
        import pytest
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        import_from_strain_tracker(conn, STRAIN_TRACKER_DB)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM effects")
        count = cur.fetchone()[0]
        conn.close()
        assert count >= 10  # At least 10 effects
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_strain_import.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the import module**

```python
# cannalchemy/data/strain_import.py
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
        if cur.lastrowid:
            strain_id_map[s["id"]] = cur.lastrowid
            stats["strains_imported"] += 1
        else:
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
        for field_name, category in [("effects", "positive"), ("negatives", "negative"), ("medical", "medical")]:
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
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_strain_import.py -v --timeout=60`

Expected: All 4 tests PASS (may take 10-30s to import 25K strains).

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/strain_import.py tests/test_strain_import.py
git commit -m "feat: add strain-tracker import with terpene/effect/composition mapping"
```

---

## Task 5: PubChem API Client

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/pubchem.py`
- Create: `~/cannalchemy/tests/test_pubchem.py`

**Step 1: Write the failing test**

```python
# tests/test_pubchem.py
import pytest
from cannalchemy.data.pubchem import lookup_compound, KNOWN_COMPOUNDS

def test_known_compounds_has_terpenes():
    """Verify we have SMILES for common terpenes."""
    assert "myrcene" in KNOWN_COMPOUNDS
    assert "limonene" in KNOWN_COMPOUNDS
    assert "caryophyllene" in KNOWN_COMPOUNDS
    assert "thc" in KNOWN_COMPOUNDS

def test_known_compounds_have_smiles():
    for name, data in KNOWN_COMPOUNDS.items():
        assert "smiles" in data, f"{name} missing SMILES"
        assert len(data["smiles"]) > 0, f"{name} has empty SMILES"

@pytest.mark.network
def test_lookup_compound_myrcene():
    """Test live PubChem lookup for myrcene."""
    result = lookup_compound("myrcene")
    assert result is not None
    assert result["cid"] > 0
    assert "molecular_weight" in result
    assert result["molecular_weight"] > 100  # myrcene MW ~136

@pytest.mark.network
def test_lookup_compound_not_found():
    result = lookup_compound("definitelynotacompound12345")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_pubchem.py -v -k "not network"`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the PubChem client**

```python
# cannalchemy/data/pubchem.py
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
```

**Step 4: Run offline tests**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_pubchem.py -v -k "not network"`

Expected: First 2 tests PASS (known compounds validation).

**Step 5: Run network test (optional, verifies live API)**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_pubchem.py -v -m network`

Expected: PASS (requires internet access).

**Step 6: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/pubchem.py tests/test_pubchem.py
git commit -m "feat: add PubChem client with cached SMILES for 27 terpenes/cannabinoids"
```

---

## Task 6: ChEMBL API Client

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/chembl.py`
- Create: `~/cannalchemy/tests/test_chembl.py`

**Step 1: Write the failing test**

```python
# tests/test_chembl.py
import pytest
from cannalchemy.data.chembl import KNOWN_RECEPTORS, KNOWN_BINDING_DATA

def test_known_receptors_has_cb1_cb2():
    assert "CB1" in KNOWN_RECEPTORS
    assert "CB2" in KNOWN_RECEPTORS
    assert "TRPV1" in KNOWN_RECEPTORS

def test_known_receptors_have_chembl_ids():
    for name, data in KNOWN_RECEPTORS.items():
        assert "chembl_id" in data, f"{name} missing chembl_id"
        assert data["chembl_id"].startswith("CHEMBL"), f"{name} has invalid chembl_id"

def test_known_binding_data_exists():
    """Verify we have pre-populated binding affinity data."""
    assert len(KNOWN_BINDING_DATA) > 0
    for entry in KNOWN_BINDING_DATA:
        assert "molecule" in entry
        assert "receptor" in entry
        assert "ki_nm" in entry or "ic50_nm" in entry or "ec50_nm" in entry

@pytest.mark.network
def test_fetch_binding_data_cb1():
    from cannalchemy.data.chembl import fetch_binding_data
    results = fetch_binding_data("CHEMBL218", limit=5)
    assert len(results) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_chembl.py -v -k "not network"`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the ChEMBL client**

```python
# cannalchemy/data/chembl.py
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
```

**Step 4: Run offline tests**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_chembl.py -v -k "not network"`

Expected: First 3 tests PASS.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/chembl.py tests/test_chembl.py
git commit -m "feat: add ChEMBL client with 6 receptors and 19 known binding affinities"
```

---

## Task 7: NetworkX Knowledge Graph

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/graph.py`
- Create: `~/cannalchemy/tests/test_graph.py`

**Step 1: Write the failing test**

```python
# tests/test_graph.py
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.chembl import seed_receptors_and_bindings
from cannalchemy.data.graph import build_knowledge_graph

def _create_test_db():
    """Create a small test DB with known data."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    conn = init_db(db_path)

    # Add molecules
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('thc', 'cannabinoid')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('cbd', 'cannabinoid')")

    # Add receptors
    conn.execute("INSERT INTO receptors (name, gene_name) VALUES ('CB1', 'CNR1')")
    conn.execute("INSERT INTO receptors (name, gene_name) VALUES ('CB2', 'CNR2')")

    # Add binding affinities
    conn.execute("INSERT INTO binding_affinities (molecule_id, receptor_id, ki_nm, action_type) VALUES (2, 1, 40.7, 'partial agonist')")
    conn.execute("INSERT INTO binding_affinities (molecule_id, receptor_id, ki_nm, action_type) VALUES (3, 2, 2860.0, 'inverse agonist')")

    # Add effects
    conn.execute("INSERT INTO effects (name, category) VALUES ('relaxed', 'positive')")
    conn.execute("INSERT INTO effects (name, category) VALUES ('euphoric', 'positive')")

    # Add a strain
    conn.execute("INSERT INTO strains (name, normalized_name, strain_type, source) VALUES ('Blue Dream', 'blue dream', 'hybrid', 'test')")

    # Add compositions
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage) VALUES (1, 1, 0.35)")
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage) VALUES (1, 2, 18.0)")

    # Add effect reports
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count) VALUES (1, 1, 100)")
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count) VALUES (1, 2, 80)")

    conn.commit()
    return conn

def test_build_graph_has_nodes():
    conn = _create_test_db()
    G = build_knowledge_graph(conn)
    conn.close()
    assert G.number_of_nodes() > 0
    assert G.number_of_edges() > 0

def test_graph_has_molecule_nodes():
    conn = _create_test_db()
    G = build_knowledge_graph(conn)
    conn.close()
    molecule_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "molecule"]
    assert len(molecule_nodes) >= 3

def test_graph_has_binding_edges():
    conn = _create_test_db()
    G = build_knowledge_graph(conn)
    conn.close()
    binding_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "binds_to"]
    assert len(binding_edges) >= 2

def test_graph_pathway_traversal():
    """Test that we can traverse from a molecule to an effect through receptors."""
    conn = _create_test_db()
    G = build_knowledge_graph(conn)
    conn.close()
    # THC -> CB1 binding exists
    assert G.has_edge("molecule:thc", "receptor:CB1")
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_graph.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the graph module**

```python
# cannalchemy/data/graph.py
"""Build NetworkX knowledge graph from SQLite data."""
import sqlite3
import networkx as nx


def build_knowledge_graph(conn: sqlite3.Connection) -> nx.DiGraph:
    """Build the molecular interaction knowledge graph.

    Node types: molecule, receptor, effect, strain
    Edge types: binds_to, contains, produces, reports

    Node IDs are prefixed: 'molecule:myrcene', 'receptor:CB1', etc.
    """
    G = nx.DiGraph()

    # Add molecule nodes
    for row in conn.execute("SELECT id, name, molecule_type, smiles, molecular_weight FROM molecules").fetchall():
        G.add_node(
            f"molecule:{row[1]}",
            node_type="molecule",
            db_id=row[0],
            name=row[1],
            molecule_type=row[2],
            smiles=row[3] or "",
            molecular_weight=row[4],
        )

    # Add receptor nodes
    for row in conn.execute("SELECT id, name, gene_name, location, function FROM receptors").fetchall():
        G.add_node(
            f"receptor:{row[1]}",
            node_type="receptor",
            db_id=row[0],
            name=row[1],
            gene_name=row[2],
            location=row[3] or "",
            function=row[4] or "",
        )

    # Add effect nodes
    for row in conn.execute("SELECT id, name, category FROM effects").fetchall():
        G.add_node(
            f"effect:{row[1]}",
            node_type="effect",
            db_id=row[0],
            name=row[1],
            category=row[2],
        )

    # Add strain nodes (only strains with compositions)
    for row in conn.execute(
        "SELECT DISTINCT s.id, s.name, s.strain_type FROM strains s "
        "JOIN strain_compositions sc ON s.id = sc.strain_id"
    ).fetchall():
        G.add_node(
            f"strain:{row[1]}",
            node_type="strain",
            db_id=row[0],
            name=row[1],
            strain_type=row[2],
        )

    # Add binding edges (molecule -> receptor)
    for row in conn.execute(
        "SELECT m.name, r.name, ba.ki_nm, ba.ic50_nm, ba.ec50_nm, ba.action_type, ba.source "
        "FROM binding_affinities ba "
        "JOIN molecules m ON ba.molecule_id = m.id "
        "JOIN receptors r ON ba.receptor_id = r.id"
    ).fetchall():
        # Convert Ki to a 0-1 affinity score (lower Ki = stronger binding)
        ki = row[2]
        affinity_score = 1.0 / (1.0 + (ki / 100.0)) if ki else 0.5
        G.add_edge(
            f"molecule:{row[0]}",
            f"receptor:{row[1]}",
            edge_type="binds_to",
            ki_nm=row[2],
            ic50_nm=row[3],
            ec50_nm=row[4],
            action_type=row[5] or "",
            affinity_score=affinity_score,
            source=row[6] or "",
        )

    # Add composition edges (strain -> molecule)
    for row in conn.execute(
        "SELECT s.name, m.name, sc.percentage, sc.measurement_type "
        "FROM strain_compositions sc "
        "JOIN strains s ON sc.strain_id = s.id "
        "JOIN molecules m ON sc.molecule_id = m.id"
    ).fetchall():
        strain_node = f"strain:{row[0]}"
        mol_node = f"molecule:{row[1]}"
        if G.has_node(strain_node) and G.has_node(mol_node):
            G.add_edge(
                strain_node, mol_node,
                edge_type="contains",
                percentage=row[2],
                measurement_type=row[3] or "",
            )

    # Add effect report edges (strain -> effect)
    for row in conn.execute(
        "SELECT s.name, e.name, er.report_count, er.source "
        "FROM effect_reports er "
        "JOIN strains s ON er.strain_id = s.id "
        "JOIN effects e ON er.effect_id = e.id"
    ).fetchall():
        strain_node = f"strain:{row[0]}"
        effect_node = f"effect:{row[1]}"
        if G.has_node(strain_node) and G.has_node(effect_node):
            G.add_edge(
                strain_node, effect_node,
                edge_type="reports",
                report_count=row[2],
                source=row[3] or "",
            )

    return G


def get_molecule_pathways(G: nx.DiGraph, molecule_name: str) -> list[dict]:
    """Get all pathways from a molecule to effects through receptors.

    Returns list of pathway dicts:
    {molecule, receptor, affinity, action_type, connected_effects}
    """
    mol_node = f"molecule:{molecule_name}"
    if not G.has_node(mol_node):
        return []

    pathways = []
    for _, receptor_node, binding_data in G.edges(mol_node, data=True):
        if binding_data.get("edge_type") != "binds_to":
            continue

        pathway = {
            "molecule": molecule_name,
            "receptor": G.nodes[receptor_node]["name"],
            "ki_nm": binding_data.get("ki_nm"),
            "affinity_score": binding_data.get("affinity_score"),
            "action_type": binding_data.get("action_type"),
            "receptor_function": G.nodes[receptor_node].get("function", ""),
        }
        pathways.append(pathway)

    return pathways


def get_strain_profile(G: nx.DiGraph, strain_name: str) -> dict:
    """Get complete profile for a strain: compositions, effects, pathways."""
    strain_node = f"strain:{strain_name}"
    if not G.has_node(strain_node):
        return {}

    profile = {
        "name": strain_name,
        "type": G.nodes[strain_node].get("strain_type"),
        "compositions": [],
        "effects": [],
        "pathways": [],
    }

    for _, target, data in G.edges(strain_node, data=True):
        if data.get("edge_type") == "contains":
            mol_name = G.nodes[target]["name"]
            profile["compositions"].append({
                "molecule": mol_name,
                "percentage": data["percentage"],
                "type": G.nodes[target].get("molecule_type"),
            })
            # Get pathways for this molecule
            mol_pathways = get_molecule_pathways(G, mol_name)
            profile["pathways"].extend(mol_pathways)

        elif data.get("edge_type") == "reports":
            profile["effects"].append({
                "effect": G.nodes[target]["name"],
                "report_count": data.get("report_count", 0),
                "category": G.nodes[target].get("category"),
            })

    # Sort by percentage/count
    profile["compositions"].sort(key=lambda x: x["percentage"], reverse=True)
    profile["effects"].sort(key=lambda x: x["report_count"], reverse=True)

    return profile
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_graph.py -v`

Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/graph.py tests/test_graph.py
git commit -m "feat: add NetworkX knowledge graph with pathway traversal"
```

---

## Task 8: Data Pipeline CLI

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/pipeline.py`
- Create: `~/cannalchemy/tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
# tests/test_pipeline.py
import tempfile
import os
import pytest
from cannalchemy.data.pipeline import run_pipeline, PipelineConfig

STRAIN_TRACKER_DB = "/srv/appdata/strain-tracker/strain-tracker.db"

def test_pipeline_creates_database():
    if not os.path.exists(STRAIN_TRACKER_DB):
        pytest.skip("Strain tracker DB not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "cannalchemy.db")
        config = PipelineConfig(
            db_path=db_path,
            strain_tracker_db=STRAIN_TRACKER_DB,
            skip_pubchem_api=True,  # Don't hit API in tests
        )
        stats = run_pipeline(config)
        assert os.path.exists(db_path)
        assert stats["strains_imported"] > 20000
        assert stats["receptors_created"] > 0
        assert stats["bindings_created"] > 0

def test_pipeline_without_strain_tracker():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "cannalchemy.db")
        config = PipelineConfig(
            db_path=db_path,
            strain_tracker_db=None,
            skip_pubchem_api=True,
        )
        stats = run_pipeline(config)
        assert os.path.exists(db_path)
        # Should still have molecules and receptors from seed data
        assert stats["receptors_created"] > 0
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_pipeline.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the pipeline**

```python
# cannalchemy/data/pipeline.py
"""Data pipeline: orchestrates import, enrichment, and graph building."""
from dataclasses import dataclass, field
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
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_pipeline.py -v --timeout=120`

Expected: Both tests PASS.

**Step 5: Add a CLI entry point**

Add to `pyproject.toml`:

```toml
[project.scripts]
cannalchemy = "cannalchemy.data.pipeline:main"
```

Add `main()` to the bottom of `pipeline.py`:

```python
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
```

**Step 6: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/pipeline.py tests/test_pipeline.py pyproject.toml
git commit -m "feat: add data pipeline orchestrator with CLI entry point"
```

---

## Task 9: Exploratory Notebook

**Files:**
- Create: `~/cannalchemy/notebooks/01-data-exploration.ipynb`

**Step 1: Install notebook dependencies**

Run: `cd ~/cannalchemy && .venv/bin/pip install jupyter matplotlib seaborn`

**Step 2: Run the pipeline to generate the database**

Run: `cd ~/cannalchemy && .venv/bin/python -m cannalchemy.data.pipeline --db-path data/processed/cannalchemy.db --skip-pubchem`

Expected: Prints stats showing 25K+ strains imported, 6 receptors, 19 bindings.

**Step 3: Create the exploration notebook**

Create `notebooks/01-data-exploration.ipynb` with cells exploring:
1. Data quality overview (strains per source, terpene coverage, effect distribution)
2. Terpene frequency distribution (which terpenes are most/least common)
3. Terpene-effect correlation matrix (heatmap: which terpenes correlate with which effects)
4. Knowledge graph visualization (molecules -> receptors -> effects)
5. Strain clustering by terpene profile (PCA or t-SNE on terpene vectors)

Note: The notebook content should be written interactively. The key cells are:
- Load the database and build the graph
- Query terpene distributions with pandas
- Plot terpene frequency with matplotlib
- Compute and visualize correlation matrix with seaborn heatmap
- Visualize knowledge graph with networkx + matplotlib

**Step 4: Commit**

```bash
cd ~/cannalchemy
git add notebooks/01-data-exploration.ipynb data/processed/.gitkeep
git commit -m "feat: add data exploration notebook with terpene-effect analysis"
```

---

## Task 10: Final Integration Test + README Update

**Step 1: Run full test suite**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/ -v --timeout=120`

Expected: All tests PASS.

**Step 2: Run the pipeline end-to-end**

Run: `cd ~/cannalchemy && .venv/bin/python -m cannalchemy.data.pipeline --db-path data/processed/cannalchemy.db --skip-pubchem`

Expected: Complete output with all stats.

**Step 3: Update README with actual stats**

Update `README.md` with real numbers from the pipeline output.

**Step 4: Final commit**

```bash
cd ~/cannalchemy
git add -A
git commit -m "feat: complete Phase 1 data foundation

- 25K+ strains imported from Strain Tracker
- 27 molecules (21 terpenes + 6 cannabinoids) with SMILES
- 6 receptors (CB1, CB2, TRPV1, 5-HT1A, PPARgamma, GPR55)
- 19 literature-sourced binding affinities
- NetworkX knowledge graph with pathway traversal
- Strain name normalization with fuzzy matching
- Data pipeline CLI: cannalchemy --db-path <path>
- Exploratory notebook with terpene-effect correlations"
```

---

## Checkpoint Summary

After completing all 10 tasks, the cannalchemy project will have:

| Component | Status |
|-----------|--------|
| Package structure | pyproject.toml, installable |
| SQLite schema | 9 tables, indexed |
| Strain import | 25K+ strains from strain-tracker |
| Molecule data | 27 compounds with SMILES from PubChem |
| Receptor data | 6 receptors with binding affinities |
| Knowledge graph | NetworkX with pathway traversal |
| Name normalization | Fuzzy matching for strain dedup |
| Data pipeline | CLI orchestrator |
| Tests | 20+ tests covering all modules |
| Notebook | Exploratory analysis with visualizations |

**Next:** Phase 2 (Effect Prediction) — train XGBoost ensemble models on the data foundation.
