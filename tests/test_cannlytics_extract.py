"""Tests for per-state Cannlytics data extractors."""
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
    myrcene = next((m for m in measurements if m["molecule"] == "myrcene"), None)
    assert myrcene is not None
    assert myrcene["concentration"] == 0.65
    linalool = next((m for m in measurements if m["molecule"] == "linalool"), None)
    assert linalool is None

def test_extract_json_ca_style():
    """CA-style JSON results field."""
    import json
    results_json = json.dumps([
        {"key": "beta_myrcene", "value": 0.65, "units": "percent"},
        {"key": "alpha_pinene", "value": "ND", "units": "percent"},
        {"key": "delta_9_thc", "value": 22.5, "units": "percent"},
        {"key": "abamectin", "value": "ND", "units": "ug/g"},
    ])
    row = pd.Series({
        "product_name": "OG Kush",
        "results": results_json,
    })
    measurements = extract_json_measurements(row)
    assert len(measurements) >= 2
    myrcene = next((m for m in measurements if m["molecule"] == "myrcene"), None)
    assert myrcene is not None
    assert myrcene["concentration"] == 0.65

def test_extract_measurements_delegates():
    """extract_measurements picks the right extractor."""
    row = pd.Series({
        "product_name": "Test",
        "beta_myrcene": 0.5,
    })
    measurements = extract_measurements(row, "flat")
    assert len(measurements) >= 1
    assert measurements[0]["molecule"] == "myrcene"

def test_extract_returns_unit():
    """Measurements include unit field."""
    row = pd.Series({"product_name": "Test", "beta_myrcene": 0.5})
    measurements = extract_flat_measurements(row)
    assert measurements[0]["unit"] == "percent"

def test_extract_json_python_dict_notation():
    """WA-style Python dict notation (single quotes) instead of JSON."""
    results_str = "[{'key': '9_thc', 'value': 22.5, 'units': 'percent'}, {'key': 'cbd', 'value': 0.3, 'units': 'percent'}]"
    row = pd.Series({
        "product_name": "Test Strain",
        "results": results_str,
    })
    measurements = extract_json_measurements(row)
    assert len(measurements) == 2
    thc = next((m for m in measurements if m["molecule"] == "thc"), None)
    assert thc is not None
    assert thc["concentration"] == 22.5
