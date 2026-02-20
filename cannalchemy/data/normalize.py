"""Strain name normalization and fuzzy matching."""
import re
from rapidfuzz import fuzz, process


def normalize_strain_name(name: str) -> str:
    """Normalize a strain name for deduplication.

    Lowercases, strips whitespace, removes punctuation except spaces,
    collapses multiple spaces.
    """
    name = name.lower().strip()
    # Remove periods (abbreviations like O.G. → OG)
    name = name.replace('.', '')
    # Replace hyphens, underscores, hash symbols with spaces
    name = re.sub(r'[\-_#\'\"()]', ' ', name)
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
