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
