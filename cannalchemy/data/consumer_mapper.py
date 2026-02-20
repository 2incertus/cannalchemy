"""Map consumer effect names (Leafly/AllBud) to canonical effects.

Pipeline: normalize -> exact match -> synonym match -> fuzzy match -> unmapped.
"""
import json
import sqlite3

from rapidfuzz import fuzz, process


def build_effect_lookup(conn: sqlite3.Connection) -> dict:
    """Build lookup dict from canonical_effects table.

    Returns dict with:
    - canonical names as keys -> {"id": int, "canonical_name": str, "category": str}
    - synonyms as keys -> {"id": int, "canonical_name": str, "category": str}

    Should have 52+ entries (52 canonical + all synonyms).
    """
    lookup: dict[str, dict] = {}
    rows = conn.execute(
        "SELECT id, name, category, synonyms FROM canonical_effects"
    ).fetchall()

    for ce_id, name, category, synonyms_json in rows:
        entry = {"id": ce_id, "canonical_name": name, "category": category}
        lookup[name] = entry
        for syn in json.loads(synonyms_json or "[]"):
            syn_lower = syn.lower().strip()
            if syn_lower not in lookup:
                lookup[syn_lower] = {
                    "id": ce_id,
                    "canonical_name": name,
                    "category": category,
                }

    return lookup


def _normalize_consumer_effect(name: str) -> str:
    """Normalize a consumer effect name for matching.

    Lowercase, strip whitespace, replace spaces with hyphens.

    Examples:
        'Dry Mouth'        -> 'dry-mouth'
        'Lack of Appetite' -> 'lack-of-appetite'
        'HAPPY'            -> 'happy'
    """
    return name.lower().strip().replace(" ", "-")


def map_effect_name(name: str, lookup: dict) -> dict | None:
    """Map a single consumer effect name to a canonical effect.

    Pipeline:
        1. Normalize (lowercase, hyphenate) -> exact match in lookup
        2. Try lowercased original (no hyphenation) -> synonym match in lookup
        3. Fuzzy match with rapidfuzz (score >= 85) against canonical names only
        4. Return None if unmapped

    Returns:
        Dict with canonical_name, canonical_id, category, method
        or None if no match found.
    """
    normalized = _normalize_consumer_effect(name)

    # Step 1: Exact match (normalized form)
    if normalized in lookup:
        entry = lookup[normalized]
        # If the key IS the canonical name, it's an exact match;
        # if it's a synonym key, report as synonym.
        method = "exact" if entry["canonical_name"] == normalized else "synonym"
        return {
            "canonical_name": entry["canonical_name"],
            "canonical_id": entry["id"],
            "category": entry["category"],
            "method": method,
        }

    # Step 2: Synonym match (lowercased, no hyphenation)
    lowered = name.lower().strip()
    if lowered in lookup:
        entry = lookup[lowered]
        return {
            "canonical_name": entry["canonical_name"],
            "canonical_id": entry["id"],
            "category": entry["category"],
            "method": "synonym",
        }

    # Step 3: Fuzzy match against canonical names only
    canonical_names = [k for k, v in lookup.items() if v["canonical_name"] == k]
    match = process.extractOne(
        normalized, canonical_names, scorer=fuzz.ratio, score_cutoff=85
    )
    if match:
        entry = lookup[match[0]]
        return {
            "canonical_name": entry["canonical_name"],
            "canonical_id": entry["id"],
            "category": entry["category"],
            "method": "fuzzy",
        }

    return None


def map_effects_batch(names: list[str], lookup: dict) -> dict:
    """Map a batch of consumer effect names.

    Args:
        names: List of raw effect names from consumer sites.
        lookup: Lookup dict from build_effect_lookup().

    Returns:
        Dict with:
        - "mapped": list of dicts (canonical_name, canonical_id, category, method, original_name)
        - "unmapped": list of raw names that could not be matched
    """
    mapped: list[dict] = []
    unmapped: list[str] = []

    for name in names:
        result = map_effect_name(name, lookup)
        if result:
            result["original_name"] = name
            mapped.append(result)
        else:
            unmapped.append(name)

    return {"mapped": mapped, "unmapped": unmapped}
