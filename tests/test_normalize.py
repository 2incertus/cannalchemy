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
