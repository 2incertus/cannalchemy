"""Extract effect mentions from Leafly user review texts.

Two-stage extraction:
  1. Regex: match whole words from canonical effects + all synonyms
  2. LLM fallback: batch reviews through Z.AI for canonical effect extraction

Aggregation function counts effect mentions across reviews per strain.
"""
import json
import logging
import os
import re
from collections import Counter
from typing import Any

import httpx

from cannalchemy.data.taxonomy import CANONICAL_EFFECTS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Build word lists from taxonomy
# ---------------------------------------------------------------------------

def _build_word_lists() -> dict[str, list[str]]:
    """Build mapping from canonical effect name to list of matchable words.

    Returns:
        Dict mapping canonical name -> list of all terms (name + synonyms).
    """
    word_lists: dict[str, list[str]] = {}
    for effect in CANONICAL_EFFECTS:
        name = effect["name"]
        terms = [name] + list(effect.get("synonyms", []))
        word_lists[name] = terms
    return word_lists


def _build_regex_patterns() -> list[tuple[str, re.Pattern]]:
    """Build compiled regex patterns for each canonical effect.

    Each pattern matches any of the effect's terms as whole words
    (case-insensitive). Multi-word terms with hyphens are matched
    both hyphenated and space-separated.

    Returns:
        List of (canonical_name, compiled_pattern) tuples.
    """
    word_lists = _build_word_lists()
    patterns: list[tuple[str, re.Pattern]] = []

    for canonical_name, terms in word_lists.items():
        alternatives = []
        for term in terms:
            # Allow both hyphen and space forms: "dry-mouth" matches "dry mouth"
            escaped = re.escape(term)
            escaped = escaped.replace(r"\-", r"[\s\-]")
            alternatives.append(escaped)
        pattern_str = r"\b(?:" + "|".join(alternatives) + r")\b"
        patterns.append((canonical_name, re.compile(pattern_str, re.IGNORECASE)))

    return patterns


# Module-level cache
_PATTERNS: list[tuple[str, re.Pattern]] | None = None


def _get_patterns() -> list[tuple[str, re.Pattern]]:
    global _PATTERNS
    if _PATTERNS is None:
        _PATTERNS = _build_regex_patterns()
    return _PATTERNS


# ---------------------------------------------------------------------------
# Stage 1: Regex extraction
# ---------------------------------------------------------------------------

def extract_effects_regex(text: str) -> dict[str, list[str]]:
    """Extract canonical effects mentioned in review text via regex.

    Args:
        text: Raw review text.

    Returns:
        Dict with keys "positive", "negative", "medical" containing
        lists of canonical effect names found.
    """
    if not text or not text.strip():
        return {"positive": [], "negative": [], "medical": []}

    patterns = _get_patterns()
    # Build category lookup
    category_map = {e["name"]: e["category"] for e in CANONICAL_EFFECTS}

    found: dict[str, list[str]] = {"positive": [], "negative": [], "medical": []}

    for canonical_name, pattern in patterns:
        if pattern.search(text):
            cat = category_map[canonical_name]
            if canonical_name not in found[cat]:
                found[cat].append(canonical_name)

    return found


# ---------------------------------------------------------------------------
# Stage 2: LLM extraction via Z.AI
# ---------------------------------------------------------------------------

_CANONICAL_NAMES = [e["name"] for e in CANONICAL_EFFECTS]

_LLM_SYSTEM_PROMPT = (
    "You are a cannabis effect extraction assistant. Given user review texts, "
    "identify which of these 52 canonical effects are mentioned or strongly implied:\n\n"
    + ", ".join(_CANONICAL_NAMES)
    + "\n\nRespond with a JSON array of arrays. Each inner array contains the "
    "canonical effect names found in the corresponding review text. "
    "Only use names from the list above. If no effects found, return an empty array []."
)


def extract_effects_llm(
    texts: list[str],
    api_key: str | None = None,
    base_url: str = "https://api.z.ai/api/anthropic/v1/messages",
    model: str = "glm-4.7-flash",
) -> list[list[str]]:
    """Extract effects from multiple review texts via LLM.

    Args:
        texts: List of review text strings.
        api_key: Z.AI API key. Falls back to ZAI_API_KEY env var.
        base_url: API endpoint URL.
        model: Model to use.

    Returns:
        List of lists of canonical effect names, one per input text.
    """
    if not api_key:
        api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        logger.warning("No ZAI_API_KEY set, skipping LLM extraction")
        return [[] for _ in texts]

    # Build user prompt with numbered reviews
    user_parts = []
    for i, text in enumerate(texts):
        # Truncate very long reviews
        trimmed = text[:500] if len(text) > 500 else text
        user_parts.append(f"Review {i+1}: {trimmed}")
    user_msg = "\n\n".join(user_parts)

    try:
        resp = httpx.post(
            base_url,
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": model,
                "max_tokens": 2048,
                "system": _LLM_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}],
            },
            timeout=60.0,
        )
        if resp.status_code != 200:
            logger.error("LLM API returned %d: %s", resp.status_code, resp.text[:200])
            return [[] for _ in texts]

        data = resp.json()
        content = data.get("content", [{}])[0].get("text", "")

        # Parse JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        result = json.loads(content)
        if not isinstance(result, list):
            logger.warning("LLM returned non-list: %s", type(result))
            return [[] for _ in texts]

        # Validate: only keep canonical names
        canonical_set = set(_CANONICAL_NAMES)
        validated = []
        for item in result:
            if isinstance(item, list):
                validated.append([n for n in item if n in canonical_set])
            else:
                validated.append([])

        # Pad if response is shorter than input
        while len(validated) < len(texts):
            validated.append([])

        return validated[:len(texts)]

    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
        logger.error("LLM extraction failed: %s", e)
        return [[] for _ in texts]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_strain_effects(
    reviews: list[dict[str, Any]],
) -> dict[str, int]:
    """Aggregate effect mentions across reviews for one strain.

    Args:
        reviews: List of dicts with "effects" key containing
                 {"positive": [...], "negative": [...], "medical": [...]}.

    Returns:
        Dict mapping canonical effect name -> total mention count.
    """
    counts: Counter = Counter()
    for review in reviews:
        effects = review.get("effects", {})
        for cat in ("positive", "negative", "medical"):
            for name in effects.get(cat, []):
                counts[name] += 1
    return dict(counts)
