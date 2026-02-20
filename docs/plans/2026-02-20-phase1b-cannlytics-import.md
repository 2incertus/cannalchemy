# Phase 1B: Cannlytics Lab Data Import — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Import lab-tested terpene and cannabinoid concentrations from the Cannlytics HuggingFace dataset into the `lab_results` table, cross-reference with existing strains, and aggregate into `strain_compositions`.

**Architecture:** Per-state adapters extract analyte measurements from either flat CSV columns (NV, MD) or nested JSON `results` fields (CA, WA, MA). A unified value cleaner handles "ND", "<LLOQ", sentinel values, and string→float conversion. Strain matching uses existing `normalize_strain_name()` + rapidfuzz. Aggregation computes median per strain+molecule pair.

**Tech Stack:** Python 3.12, pandas, huggingface_hub, openpyxl (for .xlsx), rapidfuzz, existing cannalchemy modules

**Design doc:** `docs/plans/2026-02-20-dataset-enrichment-design.md`

**Data source:** `cannlytics/cannabis_results` on HuggingFace (CC BY 4.0)

---

## Key Findings from Data Exploration

Schema varies dramatically per state. Prioritized by terpene richness:

| State | Records | Strain Name | Terpene Data | Format | Priority |
|-------|---------|-------------|--------------|--------|----------|
| NV | 153K | product_name | **Flat columns** (88% coverage, 13 terpenes) | CSV | **HIGH** |
| CA | 72K | strain_name (sparse) + product_name | **JSON results** (full panel, 157 analytes) | CSV | **HIGH** |
| MD | 105K | strain_name (100%) | Only `total_terpenes` (no individual) | CSV | **MEDIUM** |
| WA | 203K | strain_name (84%) | **JSON results** (cannabinoids only, sparse terpenes) | XLSX | **MEDIUM** |
| MA | 75K | No strain_name | **JSON results** (terpene coverage TBD) | CSV | **MEDIUM** |
| OR | 197K | No strain_name | Only THC/CBD | CSV | **SKIP** |
| MI | 90K | No strain_name | Only total_thc (13 cols total) | CSV | **SKIP** |

**Decision:** Import NV, CA, MD, WA, MA (608K records). Skip OR and MI (no terpene data, no strain names). OR and MI only have THC potency data which doesn't help our terpene→effect prediction model.

## Molecule Name Mapping

Our 27 molecules → Cannlytics column keys:

```python
MOLECULE_COLUMN_MAP = {
    # Cannabinoids
    "thc": ["delta_9_thc", "9_thc"],
    "cbd": ["cbd"],
    "cbn": ["cbn"],
    "cbg": ["cbg"],
    "cbc": ["cbc"],
    "thcv": ["thcv"],
    # Terpenes
    "myrcene": ["beta_myrcene"],
    "pinene": ["alpha_pinene"],
    "limonene": ["d_limonene", "limonene"],
    "linalool": ["linalool"],
    "caryophyllene": ["beta_caryophyllene"],
    "humulene": ["alpha_humulene"],
    "terpinolene": ["terpinolene"],
    "ocimene": ["alpha_ocimene", "ocimene", "beta_ocimene"],
    "bisabolol": ["alpha_bisabolol"],
    "geraniol": ["geraniol", "trans_geraniol"],
    "borneol": ["borneol"],
    "camphene": ["camphene"],
    "eucalyptol": ["eucalyptol", "cineole"],
    "fenchol": ["fenchol"],
    "guaiol": ["guaiol"],
    "nerolidol": ["nerolidol", "trans_nerolidol", "cis_nerolidol"],
    "terpineol": ["terpineol", "alpha_terpineol"],
    "valencene": ["valencene"],
    "phellandrene": ["alpha_phellandrene"],
    "carene": ["delta_3_carene"],
    "farnesene": ["trans_beta_farnesene"],
}
```

---

## Task 1: Value Cleaner & Column Mapper

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/cannlytics_config.py`
- Create: `~/cannalchemy/tests/test_cannlytics_config.py`

**Step 1: Write the failing test**

```python
# tests/test_cannlytics_config.py
from cannalchemy.data.cannlytics_config import (
    clean_analyte_value,
    MOLECULE_COLUMN_MAP,
    STATE_CONFIGS,
)

def test_clean_value_float():
    assert clean_analyte_value(0.65) == 0.65

def test_clean_value_string_float():
    assert clean_analyte_value("0.65") == 0.65

def test_clean_value_nd():
    assert clean_analyte_value("ND") is None

def test_clean_value_lloq():
    assert clean_analyte_value("<LLOQ") is None

def test_clean_value_sentinel_nd():
    # Cannlytics sentinel: 0.000000001 = Not Detected
    assert clean_analyte_value(0.000000001) is None
    assert clean_analyte_value(1e-9) is None

def test_clean_value_sentinel_loq():
    # Cannlytics sentinel: 0.0000001 = Below LOQ
    assert clean_analyte_value(0.0000001) is None
    assert clean_analyte_value(1e-7) is None

def test_clean_value_none():
    assert clean_analyte_value(None) is None
    assert clean_analyte_value(float('nan')) is None

def test_clean_value_rejects_invalid():
    assert clean_analyte_value(-1.0) is None  # negative
    assert clean_analyte_value(101.0) is None  # >100%

def test_molecule_map_covers_all():
    assert len(MOLECULE_COLUMN_MAP) == 27  # all our molecules

def test_state_configs_exist():
    assert "nv" in STATE_CONFIGS
    assert "ca" in STATE_CONFIGS
    assert "md" in STATE_CONFIGS
    assert "wa" in STATE_CONFIGS
    assert "ma" in STATE_CONFIGS

def test_state_config_has_required_fields():
    for state, cfg in STATE_CONFIGS.items():
        assert "format" in cfg, f"{state} missing format"
        assert "data_source" in cfg, f"{state} missing data_source"
        assert "strain_field" in cfg, f"{state} missing strain_field"
        assert cfg["format"] in ("flat", "json_results"), f"{state} bad format"
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_config.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the config module**

```python
# cannalchemy/data/cannlytics_config.py
"""Cannlytics dataset configuration: column mapping, value cleaning, per-state configs."""
import math


# Map our molecule names to possible Cannlytics column keys
MOLECULE_COLUMN_MAP = {
    # Cannabinoids
    "thc": ["delta_9_thc", "9_thc"],
    "cbd": ["cbd"],
    "cbn": ["cbn"],
    "cbg": ["cbg"],
    "cbc": ["cbc"],
    "thcv": ["thcv"],
    # Terpenes
    "myrcene": ["beta_myrcene"],
    "pinene": ["alpha_pinene"],
    "limonene": ["d_limonene", "limonene"],
    "linalool": ["linalool"],
    "caryophyllene": ["beta_caryophyllene"],
    "humulene": ["alpha_humulene"],
    "terpinolene": ["terpinolene"],
    "ocimene": ["alpha_ocimene", "ocimene", "beta_ocimene"],
    "bisabolol": ["alpha_bisabolol"],
    "geraniol": ["geraniol", "trans_geraniol"],
    "borneol": ["borneol"],
    "camphene": ["camphene"],
    "eucalyptol": ["eucalyptol", "cineole"],
    "fenchol": ["fenchol"],
    "guaiol": ["guaiol"],
    "nerolidol": ["nerolidol", "trans_nerolidol", "cis_nerolidol"],
    "terpineol": ["terpineol", "alpha_terpineol"],
    "valencene": ["valencene"],
    "phellandrene": ["alpha_phellandrene"],
    "carene": ["delta_3_carene"],
    "farnesene": ["trans_beta_farnesene"],
}

# Sentinel values used by Cannlytics
_SENTINEL_ND = 1e-9   # 0.000000001 = Not Detected
_SENTINEL_LOQ = 1e-7  # 0.0000001 = Below LOQ
_SENTINEL_TOLERANCE = 1e-10

# Non-numeric strings that mean "no data"
_NULL_STRINGS = {"nd", "<lloq", "<lod", "n/a", "na", "none", "", "nan", "pass", "nt"}

# Per-state configuration
STATE_CONFIGS = {
    "nv": {
        "format": "flat",
        "file": "data/nv/nv-results-latest.csv",
        "file_type": "csv",
        "data_source": "flat columns",
        "strain_field": "product_name",
        "expected_records": 153064,
    },
    "ca": {
        "format": "json_results",
        "file": "data/ca/ca-results-latest.csv",
        "file_type": "csv",
        "data_source": "JSON results field",
        "strain_field": "product_name",  # strain_name is sparse
        "expected_records": 71581,
    },
    "md": {
        "format": "flat",
        "file": "data/md/md-results-latest.csv",
        "file_type": "csv",
        "data_source": "flat columns",
        "strain_field": "strain_name",
        "expected_records": 105013,
    },
    "wa": {
        "format": "json_results",
        "file": "data/wa/wa-results-latest.xlsx",
        "file_type": "xlsx",
        "data_source": "JSON results field",
        "strain_field": "strain_name",
        "expected_records": 202812,
    },
    "ma": {
        "format": "json_results",
        "file": "data/ma/ma-results-latest.csv",
        "file_type": "csv",
        "data_source": "JSON results field",
        "strain_field": "product_name",  # no strain_name column
        "expected_records": 75164,
    },
}


def clean_analyte_value(value) -> float | None:
    """Clean a raw analyte value from Cannlytics data.

    Returns None for:
    - NaN, None, empty string
    - "ND", "<LLOQ", "<LOD", "N/A", etc.
    - Sentinel values (1e-9 = ND, 1e-7 = LOQ)
    - Values outside valid range (0-100%)

    Returns float for valid numeric concentrations.
    """
    if value is None:
        return None

    # Handle NaN (both float and numpy)
    if isinstance(value, float) and math.isnan(value):
        return None

    # Handle string values
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in _NULL_STRINGS:
            return None
        if stripped.startswith("<") or stripped.startswith(">"):
            return None
        try:
            value = float(stripped)
        except ValueError:
            return None

    # Now value should be numeric
    try:
        fval = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(fval):
        return None

    # Check sentinel values
    if abs(fval - _SENTINEL_ND) < _SENTINEL_TOLERANCE:
        return None
    if abs(fval - _SENTINEL_LOQ) < _SENTINEL_TOLERANCE:
        return None

    # Validate range (0-100% for concentration percentages)
    if fval < 0 or fval > 100:
        return None

    # Zero means not detected in practice
    if fval == 0.0:
        return None

    return round(fval, 6)
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_config.py -v`

Expected: All 12 tests PASS.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/cannlytics_config.py tests/test_cannlytics_config.py
git commit -m "feat: add Cannlytics column mapping and value cleaner

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Download Pipeline

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/cannlytics_download.py`
- Create: `~/cannalchemy/tests/test_cannlytics_download.py`

**Step 1: Write the failing test**

```python
# tests/test_cannlytics_download.py
import os
from unittest.mock import patch, MagicMock
from cannalchemy.data.cannlytics_download import download_state, get_cache_path
from cannalchemy.data.cannlytics_config import STATE_CONFIGS

def test_get_cache_path():
    path = get_cache_path("nv")
    assert "nv" in path
    assert path.endswith(".csv") or path.endswith(".xlsx")

def test_get_cache_path_invalid_state():
    import pytest
    with pytest.raises(KeyError):
        get_cache_path("xx")

def test_download_uses_hf_hub(tmp_path):
    """Test download calls huggingface_hub correctly."""
    with patch("cannalchemy.data.cannlytics_download.hf_hub_download") as mock_dl:
        mock_dl.return_value = str(tmp_path / "test.csv")
        # Create a dummy file so path exists
        (tmp_path / "test.csv").write_text("a,b\n1,2\n")
        result = download_state("nv", cache_dir=str(tmp_path))
        mock_dl.assert_called_once()
        assert result == str(tmp_path / "test.csv")
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_download.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the download module**

```python
# cannalchemy/data/cannlytics_download.py
"""Download Cannlytics data files from HuggingFace."""
import os
from huggingface_hub import hf_hub_download
from cannalchemy.data.cannlytics_config import STATE_CONFIGS

REPO_ID = "cannlytics/cannabis_results"
DEFAULT_CACHE_DIR = "data/raw/cannlytics"


def get_cache_path(state: str, cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """Get expected local path for a state's data file."""
    cfg = STATE_CONFIGS[state]  # Raises KeyError for unknown state
    ext = "xlsx" if cfg["file_type"] == "xlsx" else "csv"
    return os.path.join(cache_dir, f"{state}-results-latest.{ext}")


def download_state(state: str, cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """Download a state's data file from HuggingFace.

    Returns path to the downloaded file.
    """
    cfg = STATE_CONFIGS[state]
    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=cfg["file"],
        repo_type="dataset",
        cache_dir=os.path.join(cache_dir, "hf_cache"),
    )
    return path


def download_all_states(cache_dir: str = DEFAULT_CACHE_DIR) -> dict[str, str]:
    """Download all configured states. Returns {state: path} dict."""
    results = {}
    for state in STATE_CONFIGS:
        try:
            path = download_state(state, cache_dir)
            results[state] = path
            print(f"  Downloaded {state.upper()}: {path}")
        except Exception as e:
            print(f"  FAILED {state.upper()}: {e}")
    return results
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_download.py -v`

Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/cannlytics_download.py tests/test_cannlytics_download.py
git commit -m "feat: add Cannlytics HuggingFace download pipeline

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Per-State Data Extractors

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/cannlytics_extract.py`
- Create: `~/cannalchemy/tests/test_cannlytics_extract.py`

**Step 1: Write the failing test**

```python
# tests/test_cannlytics_extract.py
import pandas as pd
from cannalchemy.data.cannlytics_extract import (
    extract_flat_measurements,
    extract_json_measurements,
    extract_measurements,
)

def test_extract_flat_nv_style():
    """NV-style flat columns with terpene data."""
    row = pd.Series({
        "product_name": "Blue Dream",
        "beta_myrcene": 0.65,
        "alpha_pinene": 0.12,
        "d_limonene": 0.45,
        "linalool": "ND",
        "delta_9_thc": 22.5,
        "date_tested": "2023-01-15",
    })
    measurements = extract_flat_measurements(row)
    assert len(measurements) >= 3
    # Check myrcene was extracted
    myrcene = next((m for m in measurements if m["molecule"] == "myrcene"), None)
    assert myrcene is not None
    assert myrcene["concentration"] == 0.65
    # Check ND was filtered
    linalool = next((m for m in measurements if m["molecule"] == "linalool"), None)
    assert linalool is None

def test_extract_json_ca_style():
    """CA-style JSON results field."""
    import json
    results_json = json.dumps([
        {"key": "beta_myrcene", "value": 0.65, "units": "percent"},
        {"key": "alpha_pinene", "value": "ND", "units": "percent"},
        {"key": "delta_9_thc", "value": 22.5, "units": "percent"},
        {"key": "abamectin", "value": "ND", "units": "ug/g"},  # pesticide, should skip
    ])
    row = pd.Series({
        "product_name": "OG Kush",
        "results": results_json,
    })
    measurements = extract_json_measurements(row)
    assert len(measurements) >= 2  # myrcene + thc (pinene is ND)
    myrcene = next((m for m in measurements if m["molecule"] == "myrcene"), None)
    assert myrcene is not None
    assert myrcene["concentration"] == 0.65

def test_extract_measurements_delegates():
    """extract_measurements picks the right extractor."""
    row = pd.Series({
        "product_name": "Test",
        "beta_myrcene": 0.5,
    })
    # Flat format
    measurements = extract_measurements(row, "flat")
    assert len(measurements) >= 1
    assert measurements[0]["molecule"] == "myrcene"

def test_extract_returns_unit():
    """Measurements include unit field."""
    row = pd.Series({"product_name": "Test", "beta_myrcene": 0.5})
    measurements = extract_flat_measurements(row)
    assert measurements[0]["unit"] == "percent"
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_extract.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the extractor module**

```python
# cannalchemy/data/cannlytics_extract.py
"""Extract analyte measurements from Cannlytics data rows."""
import json
import pandas as pd
from cannalchemy.data.cannlytics_config import MOLECULE_COLUMN_MAP, clean_analyte_value


def _build_reverse_map() -> dict[str, str]:
    """Build cannlytics_key -> our_molecule_name map."""
    reverse = {}
    for our_name, their_keys in MOLECULE_COLUMN_MAP.items():
        for key in their_keys:
            reverse[key] = our_name
    return reverse


_REVERSE_MAP = _build_reverse_map()


def extract_flat_measurements(row: pd.Series) -> list[dict]:
    """Extract measurements from flat CSV columns (NV, MD style).

    Returns list of {"molecule": str, "concentration": float, "unit": str}.
    """
    measurements = []
    for col_name in row.index:
        our_molecule = _REVERSE_MAP.get(col_name)
        if our_molecule is None:
            continue
        value = clean_analyte_value(row[col_name])
        if value is not None:
            measurements.append({
                "molecule": our_molecule,
                "concentration": value,
                "unit": "percent",
            })
    return measurements


def extract_json_measurements(row: pd.Series) -> list[dict]:
    """Extract measurements from JSON `results` field (CA, WA, MA style).

    Returns list of {"molecule": str, "concentration": float, "unit": str}.
    """
    results_str = row.get("results", "")
    if pd.isna(results_str) or not results_str:
        return []

    try:
        results = json.loads(results_str) if isinstance(results_str, str) else results_str
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(results, list):
        return []

    measurements = []
    for entry in results:
        key = entry.get("key", "")
        our_molecule = _REVERSE_MAP.get(key)
        if our_molecule is None:
            continue
        value = clean_analyte_value(entry.get("value"))
        if value is not None:
            unit = entry.get("units", "percent") or "percent"
            measurements.append({
                "molecule": our_molecule,
                "concentration": value,
                "unit": unit,
            })
    return measurements


def extract_measurements(row: pd.Series, format_type: str) -> list[dict]:
    """Extract measurements using the appropriate strategy."""
    if format_type == "flat":
        return extract_flat_measurements(row)
    elif format_type == "json_results":
        return extract_json_measurements(row)
    else:
        raise ValueError(f"Unknown format: {format_type}")
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_extract.py -v`

Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/cannlytics_extract.py tests/test_cannlytics_extract.py
git commit -m "feat: add per-state data extractors (flat + JSON results)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Lab Results Import Pipeline

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/cannlytics_import.py`
- Create: `~/cannalchemy/tests/test_cannlytics_import.py`

**Step 1: Write the failing test**

```python
# tests/test_cannlytics_import.py
import sqlite3
import tempfile
import os
import json
import pandas as pd
from cannalchemy.data.schema import init_db
from cannalchemy.data.cannlytics_import import import_state_data

def _make_csv(tmpdir, rows):
    """Create a test CSV file."""
    path = os.path.join(tmpdir, "test.csv")
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return path

def test_import_flat_data():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        # Create test CSV with NV-style flat data
        csv_path = _make_csv(tmpdir, [
            {"product_name": "Blue Dream", "beta_myrcene": 0.65, "alpha_pinene": 0.12,
             "d_limonene": 0.45, "delta_9_thc": 22.5, "date_tested": "2023-01-15"},
            {"product_name": "OG Kush", "beta_myrcene": 0.33, "alpha_pinene": 0.08,
             "d_limonene": 0.21, "delta_9_thc": 25.0, "date_tested": "2023-01-16"},
        ])
        stats = import_state_data(conn, csv_path, "nv", format_type="flat",
                                  strain_field="product_name")
        assert stats["rows_processed"] == 2
        assert stats["measurements_inserted"] > 0
        # Check lab_results table
        count = conn.execute("SELECT COUNT(*) FROM lab_results").fetchone()[0]
        assert count > 0
        conn.close()

def test_import_json_results_data():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        results_json = json.dumps([
            {"key": "beta_myrcene", "value": 0.65, "units": "percent"},
            {"key": "delta_9_thc", "value": 22.5, "units": "percent"},
        ])
        csv_path = _make_csv(tmpdir, [
            {"product_name": "Blue Dream", "results": results_json, "date_tested": "2023-01-15"},
        ])
        stats = import_state_data(conn, csv_path, "ca", format_type="json_results",
                                  strain_field="product_name")
        assert stats["rows_processed"] == 1
        assert stats["measurements_inserted"] >= 2
        conn.close()

def test_import_skips_empty_rows():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        csv_path = _make_csv(tmpdir, [
            {"product_name": "No Data Strain", "date_tested": "2023-01-15"},
        ])
        stats = import_state_data(conn, csv_path, "nv", format_type="flat",
                                  strain_field="product_name")
        assert stats["rows_skipped"] == 1
        conn.close()

def test_import_records_provenance():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        csv_path = _make_csv(tmpdir, [
            {"product_name": "Test", "beta_myrcene": 0.5, "date_tested": "2023-01-15"},
        ])
        import_state_data(conn, csv_path, "nv", format_type="flat",
                          strain_field="product_name")
        row = conn.execute("SELECT * FROM lab_results LIMIT 1").fetchone()
        assert row is not None
        # Check state field
        assert "nv" in str(row).lower() or "NV" in str(row)
        conn.close()
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_import.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the import module**

```python
# cannalchemy/data/cannlytics_import.py
"""Import Cannlytics lab data into the lab_results table."""
import sqlite3
import pandas as pd
from cannalchemy.data.cannlytics_extract import extract_measurements
from cannalchemy.data.cannlytics_config import STATE_CONFIGS


def import_state_data(
    conn: sqlite3.Connection,
    file_path: str,
    state: str,
    format_type: str,
    strain_field: str,
    chunk_size: int = 5000,
) -> dict:
    """Import a state's Cannlytics data into lab_results.

    Reads in chunks for memory efficiency. Returns stats dict.
    """
    stats = {
        "rows_processed": 0,
        "rows_skipped": 0,
        "measurements_inserted": 0,
        "state": state,
    }

    read_fn = pd.read_csv if file_path.endswith(".csv") else pd.read_excel
    reader_kwargs = {"low_memory": False} if file_path.endswith(".csv") else {}

    for chunk in pd.read_csv(file_path, chunksize=chunk_size, **reader_kwargs) if file_path.endswith(".csv") else [pd.read_excel(file_path)]:
        for _, row in chunk.iterrows():
            stats["rows_processed"] += 1

            # Get strain/product name
            strain_name = row.get(strain_field, "")
            if pd.isna(strain_name) or not str(strain_name).strip():
                strain_name = row.get("product_name", "")
            if pd.isna(strain_name) or not str(strain_name).strip():
                stats["rows_skipped"] += 1
                continue

            strain_name = str(strain_name).strip()

            # Get test date
            date_tested = ""
            for date_col in ["date_tested", "date", "date_collected"]:
                val = row.get(date_col, "")
                if pd.notna(val) and str(val).strip():
                    date_tested = str(val).strip()[:10]
                    break

            # Get lab name
            lab_name = str(row.get("lab", row.get("lims", ""))).strip()
            if pd.isna(lab_name) or lab_name == "nan":
                lab_name = ""

            # Extract measurements
            measurements = extract_measurements(row, format_type)

            if not measurements:
                stats["rows_skipped"] += 1
                continue

            # Insert into lab_results
            for m in measurements:
                conn.execute(
                    "INSERT INTO lab_results "
                    "(strain_name, normalized_strain_name, lab_name, state, "
                    "test_date, molecule_name, concentration, unit, source_file) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        strain_name,
                        "",  # Will be normalized in Task 5
                        lab_name,
                        state.upper(),
                        date_tested,
                        m["molecule"],
                        m["concentration"],
                        m["unit"],
                        file_path,
                    ),
                )
                stats["measurements_inserted"] += 1

        conn.commit()

    return stats


def import_all_states(conn: sqlite3.Connection, file_paths: dict[str, str]) -> dict:
    """Import all downloaded states. Returns combined stats."""
    all_stats = {}
    for state, path in file_paths.items():
        cfg = STATE_CONFIGS[state]
        print(f"  Importing {state.upper()} ({cfg['format']})...")
        stats = import_state_data(
            conn, path, state,
            format_type=cfg["format"],
            strain_field=cfg["strain_field"],
        )
        all_stats[state] = stats
        print(f"    Processed: {stats['rows_processed']}, "
              f"Inserted: {stats['measurements_inserted']}, "
              f"Skipped: {stats['rows_skipped']}")
    return all_stats
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_import.py -v`

Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/cannlytics_import.py tests/test_cannlytics_import.py
git commit -m "feat: add Cannlytics lab results import pipeline

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Strain Cross-Reference

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/cannlytics_strain_match.py`
- Create: `~/cannalchemy/tests/test_cannlytics_strain_match.py`

**Step 1: Write the failing test**

```python
# tests/test_cannlytics_strain_match.py
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.cannlytics_strain_match import (
    normalize_lab_results,
    match_strains,
)

def test_normalize_lab_results():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute(
            "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
            "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
            ("Blue Dream (1g)", "", "NV", "myrcene", 0.65, "percent"),
        )
        conn.commit()
        count = normalize_lab_results(conn)
        assert count >= 1
        row = conn.execute("SELECT normalized_strain_name FROM lab_results").fetchone()
        assert row[0] == "blue dream 1g"  # normalized
        conn.close()

def test_match_existing_strains():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        # Seed an existing strain
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'strain-tracker')")
        # Add lab result
        conn.execute(
            "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
            "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
            ("Blue Dream Hybrid", "blue dream hybrid", "NV", "myrcene", 0.65, "percent"),
        )
        conn.commit()
        stats = match_strains(conn, threshold=80)
        assert stats["matched"] >= 1 or stats["created"] >= 1
        conn.close()

def test_creates_new_strains():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute(
            "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
            "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
            ("Totally Unique Strain XYZ", "totally unique strain xyz", "NV", "myrcene", 0.65, "percent"),
        )
        conn.commit()
        stats = match_strains(conn, threshold=90)
        assert stats["created"] >= 1
        # Verify new strain was created
        row = conn.execute("SELECT * FROM strains WHERE source='cannlytics'").fetchone()
        assert row is not None
        conn.close()
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_strain_match.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the strain matching module**

```python
# cannalchemy/data/cannlytics_strain_match.py
"""Match Cannlytics lab strain names to existing strains or create new ones."""
import sqlite3
from rapidfuzz import fuzz, process
from cannalchemy.data.normalize import normalize_strain_name


def normalize_lab_results(conn: sqlite3.Connection) -> int:
    """Normalize all strain names in lab_results that haven't been normalized yet.

    Returns count of rows updated.
    """
    rows = conn.execute(
        "SELECT id, strain_name FROM lab_results WHERE normalized_strain_name = ''"
    ).fetchall()

    count = 0
    for row_id, strain_name in rows:
        normalized = normalize_strain_name(strain_name)
        if normalized:
            conn.execute(
                "UPDATE lab_results SET normalized_strain_name = ? WHERE id = ?",
                (normalized, row_id),
            )
            count += 1

    conn.commit()
    return count


def match_strains(conn: sqlite3.Connection, threshold: int = 90) -> dict:
    """Match lab result strain names to existing strains or create new ones.

    Returns stats dict.
    """
    stats = {"matched": 0, "created": 0, "skipped": 0}

    # Get all existing strains for matching
    existing = conn.execute(
        "SELECT id, normalized_name FROM strains"
    ).fetchall()
    existing_map = {row[1]: row[0] for row in existing}
    existing_names = list(existing_map.keys())

    # Get distinct normalized strain names from lab_results
    lab_names = conn.execute(
        "SELECT DISTINCT normalized_strain_name FROM lab_results "
        "WHERE normalized_strain_name != ''"
    ).fetchall()
    lab_names = [row[0] for row in lab_names]

    for lab_name in lab_names:
        # Exact match first
        if lab_name in existing_map:
            stats["matched"] += 1
            continue

        # Fuzzy match
        if existing_names:
            match = process.extractOne(
                lab_name, existing_names,
                scorer=fuzz.ratio,
                score_cutoff=threshold,
            )
            if match:
                stats["matched"] += 1
                continue

        # No match — create new strain
        cur = conn.execute(
            "INSERT OR IGNORE INTO strains (name, normalized_name, strain_type, source) "
            "VALUES (?, ?, '', 'cannlytics')",
            (lab_name, lab_name),
        )
        if cur.rowcount == 1:
            stats["created"] += 1
            # Update caches for future matching
            new_id = cur.lastrowid
            existing_map[lab_name] = new_id
            existing_names.append(lab_name)
        else:
            stats["skipped"] += 1

    conn.commit()
    return stats
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_strain_match.py -v`

Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/cannlytics_strain_match.py tests/test_cannlytics_strain_match.py
git commit -m "feat: add Cannlytics strain cross-reference with fuzzy matching

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Lab-to-Composition Aggregation

**Files:**
- Create: `~/cannalchemy/cannalchemy/data/cannlytics_aggregate.py`
- Create: `~/cannalchemy/tests/test_cannlytics_aggregate.py`

**Step 1: Write the failing test**

```python
# tests/test_cannlytics_aggregate.py
import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.cannlytics_aggregate import aggregate_lab_to_compositions

def test_aggregate_computes_median():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        # Create strain + molecule
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'cannlytics')")
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
        # Add 3 lab results for same strain+molecule
        for val in [0.5, 0.6, 0.7]:
            conn.execute(
                "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
                "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
                ("Blue Dream", "blue dream", "NV", "myrcene", val, "percent"),
            )
        conn.commit()
        stats = aggregate_lab_to_compositions(conn)
        assert stats["compositions_created"] >= 1
        # Check median is 0.6
        row = conn.execute(
            "SELECT percentage FROM strain_compositions WHERE measurement_type='lab_tested'"
        ).fetchone()
        assert row is not None
        assert abs(row[0] - 0.6) < 0.01  # median of [0.5, 0.6, 0.7]
        conn.close()

def test_aggregate_tags_existing_as_reported():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        # Create strain + molecule with existing composition (no measurement_type)
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'st')")
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
        conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (1, 1, 0.5, 'strain-tracker')")
        conn.commit()
        stats = aggregate_lab_to_compositions(conn)
        # Existing should be tagged as 'reported'
        row = conn.execute(
            "SELECT measurement_type FROM strain_compositions WHERE source='strain-tracker'"
        ).fetchone()
        assert row[0] == "reported"
        conn.close()

def test_aggregate_keeps_both():
    """Lab data should coexist with reported data, not replace it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = init_db(db_path)
        conn.execute("INSERT INTO strains (name, normalized_name, source) VALUES ('Blue Dream', 'blue dream', 'st')")
        conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
        conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (1, 1, 0.5, 'strain-tracker')")
        conn.execute(
            "INSERT INTO lab_results (strain_name, normalized_strain_name, state, "
            "molecule_name, concentration, unit) VALUES (?, ?, ?, ?, ?, ?)",
            ("Blue Dream", "blue dream", "NV", "myrcene", 0.7, "percent"),
        )
        conn.commit()
        aggregate_lab_to_compositions(conn)
        count = conn.execute(
            "SELECT COUNT(*) FROM strain_compositions WHERE strain_id=1 AND molecule_id=1"
        ).fetchone()[0]
        assert count == 2  # both reported and lab_tested
        conn.close()
```

**Step 2: Run test to verify it fails**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_aggregate.py -v`

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the aggregation module**

```python
# cannalchemy/data/cannlytics_aggregate.py
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

        # Check if lab_tested composition already exists
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
```

**Step 4: Run test to verify it passes**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/test_cannlytics_aggregate.py -v`

Expected: All 3 tests PASS.

**Step 5: Run full test suite**

Run: `cd ~/cannalchemy && .venv/bin/python -m pytest tests/ -v -k "not network"`

Expected: All tests PASS.

**Step 6: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/cannlytics_aggregate.py tests/test_cannlytics_aggregate.py
git commit -m "feat: add lab-to-composition aggregation with median

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Run Import on Live Database

This task runs the full pipeline against real data. **Operational, not TDD.**

**Step 1: Download all state files**

```bash
cd ~/cannalchemy && .venv/bin/python -c "
from cannalchemy.data.cannlytics_download import download_all_states
paths = download_all_states()
for state, path in paths.items():
    print(f'{state.upper()}: {path}')
"
```

Expected: 5 files downloaded (NV, CA, MD, WA, MA).

**Step 2: Import NV first (fastest — flat columns)**

```bash
cd ~/cannalchemy && .venv/bin/python -c "
import sqlite3, json
from cannalchemy.data.cannlytics_import import import_state_data
from cannalchemy.data.cannlytics_download import download_state
from cannalchemy.data.cannlytics_config import STATE_CONFIGS

conn = sqlite3.connect('data/processed/cannalchemy.db')
path = download_state('nv')
cfg = STATE_CONFIGS['nv']
stats = import_state_data(conn, path, 'nv', cfg['format'], cfg['strain_field'])
print(json.dumps(stats, indent=2))
conn.close()
"
```

**Step 3: Import remaining states**

```bash
cd ~/cannalchemy && .venv/bin/python -c "
import sqlite3, json
from cannalchemy.data.cannlytics_import import import_state_data
from cannalchemy.data.cannlytics_download import download_state
from cannalchemy.data.cannlytics_config import STATE_CONFIGS

conn = sqlite3.connect('data/processed/cannalchemy.db')
for state in ['ca', 'md', 'wa', 'ma']:
    print(f'Importing {state.upper()}...')
    path = download_state(state)
    cfg = STATE_CONFIGS[state]
    stats = import_state_data(conn, path, state, cfg['format'], cfg['strain_field'])
    print(json.dumps(stats, indent=2))
conn.close()
"
```

**Step 4: Normalize lab result strain names**

```bash
cd ~/cannalchemy && .venv/bin/python -c "
import sqlite3
from cannalchemy.data.cannlytics_strain_match import normalize_lab_results
conn = sqlite3.connect('data/processed/cannalchemy.db')
count = normalize_lab_results(conn)
print(f'Normalized {count} lab result strain names')
conn.close()
"
```

**Step 5: Match strains and create new ones**

```bash
cd ~/cannalchemy && .venv/bin/python -c "
import sqlite3, json
from cannalchemy.data.cannlytics_strain_match import match_strains
conn = sqlite3.connect('data/processed/cannalchemy.db')
stats = match_strains(conn, threshold=90)
print(json.dumps(stats, indent=2))
conn.close()
"
```

**Step 6: Aggregate into strain_compositions**

```bash
cd ~/cannalchemy && .venv/bin/python -c "
import sqlite3, json
from cannalchemy.data.cannlytics_aggregate import aggregate_lab_to_compositions
conn = sqlite3.connect('data/processed/cannalchemy.db')
stats = aggregate_lab_to_compositions(conn)
print(json.dumps(stats, indent=2))
conn.close()
"
```

**Step 7: Verify results**

```bash
cd ~/cannalchemy && .venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/processed/cannalchemy.db')
print('=== POST-IMPORT STATS ===')
print(f'Lab results: {conn.execute(\"SELECT COUNT(*) FROM lab_results\").fetchone()[0]}')
print(f'  By state:')
for row in conn.execute('SELECT state, COUNT(*) FROM lab_results GROUP BY state ORDER BY COUNT(*) DESC'):
    print(f'    {row[0]}: {row[1]:,}')
print(f'Strains: {conn.execute(\"SELECT COUNT(*) FROM strains\").fetchone()[0]}')
print(f'  Cannlytics-created: {conn.execute(\"SELECT COUNT(*) FROM strains WHERE source=\\\"cannlytics\\\"\").fetchone()[0]}')
print(f'Strain compositions: {conn.execute(\"SELECT COUNT(*) FROM strain_compositions\").fetchone()[0]}')
print(f'  Reported: {conn.execute(\"SELECT COUNT(*) FROM strain_compositions WHERE measurement_type=\\\"reported\\\"\").fetchone()[0]}')
print(f'  Lab-tested: {conn.execute(\"SELECT COUNT(*) FROM strain_compositions WHERE measurement_type=\\\"lab_tested\\\"\").fetchone()[0]}')
print(f'Data sources: {conn.execute(\"SELECT COUNT(*) FROM data_sources\").fetchone()[0]}')

# ML readiness
ml_ready = conn.execute('''
    SELECT COUNT(DISTINCT s.id) FROM strains s
    WHERE s.id NOT IN (SELECT alias_strain_id FROM strain_aliases)
    AND EXISTS (SELECT 1 FROM strain_compositions sc WHERE sc.strain_id = s.id)
    AND EXISTS (
        SELECT 1 FROM effect_reports er
        JOIN effects e ON er.effect_id = e.id
        JOIN effect_mappings em ON e.name = em.raw_name
        WHERE er.strain_id = s.id AND em.canonical_id IS NOT NULL
    )
''').fetchone()[0]
total = conn.execute('SELECT COUNT(*) FROM strains WHERE id NOT IN (SELECT alias_strain_id FROM strain_aliases)').fetchone()[0]
print(f'ML-ready: {ml_ready} / {total} ({ml_ready*100//total if total else 0}%)')
conn.close()
"
```

**Step 8: Record in data_sources and commit**

```bash
cd ~/cannalchemy && .venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/processed/cannalchemy.db')
for state in ['nv', 'ca', 'md', 'wa', 'ma']:
    count = conn.execute('SELECT COUNT(*) FROM lab_results WHERE state=?', (state.upper(),)).fetchone()[0]
    conn.execute(
        'INSERT OR IGNORE INTO data_sources (name, source_type, url, record_count, notes) VALUES (?, ?, ?, ?, ?)',
        (f'cannlytics_{state}', 'lab_results', 'https://huggingface.co/datasets/cannlytics/cannabis_results',
         count, f'{state.upper()} lab test results, CC BY 4.0')
    )
conn.commit()
conn.close()
"
git add .gitignore
git commit -m "chore: complete Phase 1B Cannlytics lab data import

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Checkpoint Summary

After completing all 7 tasks:

| Component | Before (post-1A) | Target |
|-----------|-------------------|--------|
| Lab results | 0 | 200K+ measurements |
| Strains (total) | 23,329 unique | 30K+ (new from Cannlytics) |
| Strain compositions | 78,697 (reported) | 78K reported + new lab_tested |
| Measurement types | none | 'reported' + 'lab_tested' |
| States imported | 0 | 5 (NV, CA, MD, WA, MA) |
| New modules | 0 | 5 (config, download, extract, import, aggregate, strain_match) |
| Tests | 51 | 65+ |

**Next:** Phase 1C (Leafly + AllBud Consumer Data)
