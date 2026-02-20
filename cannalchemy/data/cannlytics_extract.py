"""Extract analyte measurements from Cannlytics data rows."""
import ast
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
        # WA Excel stores Python dict notation (single quotes) instead of JSON
        try:
            results = ast.literal_eval(results_str) if isinstance(results_str, str) else []
        except (ValueError, SyntaxError):
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
