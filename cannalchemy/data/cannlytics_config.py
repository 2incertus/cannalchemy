"""Cannlytics dataset configuration: column mapping, value cleaning, per-state configs."""
import math


MOLECULE_COLUMN_MAP = {
    "thc": ["delta_9_thc", "9_thc"],
    "cbd": ["cbd"],
    "cbn": ["cbn"],
    "cbg": ["cbg"],
    "cbc": ["cbc"],
    "thcv": ["thcv"],
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

_SENTINEL_ND = 1e-9
_SENTINEL_LOQ = 1e-7
_SENTINEL_TOLERANCE = 1e-10

_NULL_STRINGS = {"nd", "<lloq", "<lod", "n/a", "na", "none", "", "nan", "pass", "nt"}

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
        "strain_field": "product_name",
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
        "strain_field": "product_name",
        "expected_records": 75164,
    },
}


def clean_analyte_value(value) -> float | None:
    """Clean a raw analyte value from Cannlytics data.

    Returns None for NaN, None, "ND", "<LLOQ", sentinel values, or out-of-range.
    Returns float for valid numeric concentrations.
    """
    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

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

    try:
        fval = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(fval):
        return None

    if abs(fval - _SENTINEL_ND) < _SENTINEL_TOLERANCE:
        return None
    if abs(fval - _SENTINEL_LOQ) < _SENTINEL_TOLERANCE:
        return None

    if fval < 0 or fval > 100:
        return None

    if fval == 0.0:
        return None

    return round(fval, 6)
