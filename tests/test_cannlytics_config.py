"""Tests for Cannlytics dataset configuration."""
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
    assert clean_analyte_value(0.000000001) is None
    assert clean_analyte_value(1e-9) is None

def test_clean_value_sentinel_loq():
    assert clean_analyte_value(0.0000001) is None
    assert clean_analyte_value(1e-7) is None

def test_clean_value_none():
    assert clean_analyte_value(None) is None
    assert clean_analyte_value(float('nan')) is None

def test_clean_value_rejects_invalid():
    assert clean_analyte_value(-1.0) is None
    assert clean_analyte_value(101.0) is None

def test_molecule_map_covers_all():
    assert len(MOLECULE_COLUMN_MAP) == 27

def test_state_configs_exist():
    assert "nv" in STATE_CONFIGS
    assert "ca" in STATE_CONFIGS
    assert "md" in STATE_CONFIGS
    assert "wa" in STATE_CONFIGS
    # MA skipped: results 100% NaN, no strain names, only THC flat column

def test_state_config_has_required_fields():
    for state, cfg in STATE_CONFIGS.items():
        assert "format" in cfg, f"{state} missing format"
        assert "data_source" in cfg, f"{state} missing data_source"
        assert "strain_field" in cfg, f"{state} missing strain_field"
        assert cfg["format"] in ("flat", "json_results"), f"{state} bad format"
