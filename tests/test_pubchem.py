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
