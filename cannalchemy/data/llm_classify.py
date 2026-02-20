"""Effect classification: rule-based and LLM-powered mapping to canonical taxonomy.

Maps messy raw effect names from scraped data sources into the canonical
effect taxonomy defined in taxonomy.py.  Two strategies:

1. Rule-based (classify_effects_rule_based) -- exact match, synonym lookup,
   and length-based junk filtering.  Fast, deterministic, no API needed.

2. LLM-powered (classify_effects_llm) -- sends batches of unresolved names
   to GLM-4.7 via the Z.AI Anthropic-compatible API for intelligent mapping.
"""

import json
import logging
import re
import sqlite3
from typing import Dict, List, Optional

from cannalchemy.data.taxonomy import CANONICAL_EFFECTS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_synonym_cache: Optional[Dict[str, str]] = None


def _build_synonym_map() -> Dict[str, str]:
    """Build a dict mapping all synonyms and canonical names to their canonical form.

    Returns:
        Dict mapping lowercased synonym/name -> canonical effect name.
    """
    global _synonym_cache
    if _synonym_cache is not None:
        return _synonym_cache

    mapping: Dict[str, str] = {}
    for effect in CANONICAL_EFFECTS:
        canonical_name = effect["name"]
        # Map the canonical name itself
        mapping[canonical_name.lower()] = canonical_name
        # Map all synonyms
        for synonym in effect.get("synonyms", []):
            mapping[synonym.lower()] = canonical_name
    _synonym_cache = mapping
    return mapping


# ---------------------------------------------------------------------------
# Prompt building and response parsing (used by LLM classification)
# ---------------------------------------------------------------------------


def build_classification_prompt(raw_effects: List[str]) -> str:
    """Build a prompt for the LLM with all canonical effect names listed.

    Instructs the model to map each raw effect to a canonical name or "JUNK".

    Args:
        raw_effects: List of raw effect name strings to classify.

    Returns:
        Formatted prompt string.
    """
    canonical_names = sorted({e["name"] for e in CANONICAL_EFFECTS})
    canonical_list = ", ".join(canonical_names)

    effects_list = "\n".join(f'  - "{e}"' for e in raw_effects)

    prompt = (
        "You are a cannabis effect taxonomy classifier. Your job is to map raw "
        "effect names to their canonical form.\n\n"
        f"CANONICAL EFFECTS:\n{canonical_list}\n\n"
        "RAW EFFECTS TO CLASSIFY:\n"
        f"{effects_list}\n\n"
        "INSTRUCTIONS:\n"
        "- For each raw effect, map it to the single best-matching canonical "
        "effect name from the list above.\n"
        "- If a raw effect is nonsensical, too vague, or clearly not a cannabis "
        "effect, map it to \"JUNK\".\n"
        "- Return ONLY a JSON object mapping each raw effect string to its "
        "canonical name or \"JUNK\".\n"
        "- Do not add explanations, only output the JSON.\n\n"
        "Example output:\n"
        '{"relaxing": "relaxed", "munchies": "hungry", "asdfgh": "JUNK"}'
    )
    return prompt


def parse_classification_response(response_text: str) -> Dict[str, str]:
    """Parse the JSON response from the LLM classification.

    Handles markdown code blocks (```json ... ```) and bare JSON.

    Args:
        response_text: Raw text response from the LLM.

    Returns:
        Dict mapping raw effect name -> canonical name or "JUNK".
        Returns empty dict on parse failure.
    """
    text = response_text.strip()

    # Strip markdown code fences if present
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if code_block:
        text = code_block.group(1).strip()

    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return {str(k): str(v) for k, v in result.items()}
        return {}
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse LLM classification response: %s", text[:200])
        return {}


# ---------------------------------------------------------------------------
# Rule-based classification
# ---------------------------------------------------------------------------


def classify_effects_rule_based(conn: sqlite3.Connection) -> Dict[str, int]:
    """Classify effects using exact match and synonym lookup.

    Processes all effects in the `effects` table that are NOT already in
    `effect_mappings`. Inserts matches into `effect_mappings` with:
      - exact_match: confidence=1.0, method='exact_match'
      - synonym_match: confidence=0.95, method='synonym_match'
      - length_filter (>40 chars): canonical_id=NULL, confidence=0.0, method='length_filter'

    Args:
        conn: SQLite database connection.

    Returns:
        Stats dict with exact_matches, synonym_matches, length_filtered, unmatched counts.
    """
    synonym_map = _build_synonym_map()

    # Get canonical effect name -> id mapping from DB
    canonical_ids: Dict[str, int] = {}
    for row in conn.execute("SELECT id, name FROM canonical_effects"):
        canonical_ids[row[1]] = row[0]

    # Fetch raw effects not already mapped
    unmapped = conn.execute(
        "SELECT e.name FROM effects e "
        "LEFT JOIN effect_mappings em ON e.name = em.raw_name "
        "WHERE em.id IS NULL"
    ).fetchall()

    stats = {
        "exact_matches": 0,
        "synonym_matches": 0,
        "length_filtered": 0,
        "unmatched": 0,
    }

    for (raw_name,) in unmapped:
        lower_name = raw_name.lower().strip()

        # Length filter -- strings over 40 chars are almost certainly junk
        if len(raw_name) > 40:
            conn.execute(
                "INSERT OR IGNORE INTO effect_mappings "
                "(raw_name, canonical_id, confidence, method) "
                "VALUES (?, NULL, 0.0, 'length_filter')",
                (raw_name,),
            )
            stats["length_filtered"] += 1
            continue

        # Exact match against canonical names
        if lower_name in canonical_ids:
            conn.execute(
                "INSERT OR IGNORE INTO effect_mappings "
                "(raw_name, canonical_id, confidence, method) "
                "VALUES (?, ?, 1.0, 'exact_match')",
                (raw_name, canonical_ids[lower_name]),
            )
            stats["exact_matches"] += 1
            continue

        # Synonym lookup
        canonical_name = synonym_map.get(lower_name)
        if canonical_name and canonical_name in canonical_ids:
            conn.execute(
                "INSERT OR IGNORE INTO effect_mappings "
                "(raw_name, canonical_id, confidence, method) "
                "VALUES (?, ?, 0.95, 'synonym_match')",
                (raw_name, canonical_ids[canonical_name]),
            )
            stats["synonym_matches"] += 1
            continue

        # No match found
        stats["unmatched"] += 1

    conn.commit()

    logger.info(
        "Rule-based classification: %d exact, %d synonym, %d length-filtered, %d unmatched",
        stats["exact_matches"],
        stats["synonym_matches"],
        stats["length_filtered"],
        stats["unmatched"],
    )
    return stats


# ---------------------------------------------------------------------------
# LLM-powered classification
# ---------------------------------------------------------------------------


def classify_effects_llm(
    conn: sqlite3.Connection,
    api_key: str,
    batch_size: int = 40,
) -> Dict[str, int]:
    """Classify unmapped effects using GLM-4.7 via Z.AI API.

    Sends batches of raw effect names to the LLM for classification.
    Uses the Anthropic-compatible API at https://api.z.ai/api/anthropic/v1/messages.

    Args:
        conn: SQLite database connection.
        api_key: Z.AI API key.
        batch_size: Number of effects to classify per API call.

    Returns:
        Stats dict with llm_mapped, llm_junk, llm_failed counts.
    """
    import httpx

    # Get canonical effect name -> id mapping from DB
    canonical_ids: Dict[str, int] = {}
    for row in conn.execute("SELECT id, name FROM canonical_effects"):
        canonical_ids[row[1]] = row[0]

    # Fetch raw effects not already mapped
    unmapped = conn.execute(
        "SELECT e.name FROM effects e "
        "LEFT JOIN effect_mappings em ON e.name = em.raw_name "
        "WHERE em.id IS NULL"
    ).fetchall()
    unmapped_names = [row[0] for row in unmapped]

    stats = {"llm_mapped": 0, "llm_junk": 0, "llm_failed": 0}

    if not unmapped_names:
        logger.info("No unmapped effects to classify via LLM.")
        return stats

    # Process in batches
    for i in range(0, len(unmapped_names), batch_size):
        batch = unmapped_names[i : i + batch_size]
        prompt = build_classification_prompt(batch)

        try:
            response = httpx.post(
                "https://api.z.ai/api/anthropic/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "glm-4.7",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60.0,
            )
            response.raise_for_status()

            result = response.json()
            # Extract text from Anthropic-format response
            text_content = ""
            for block in result.get("content", []):
                if block.get("type") == "text":
                    text_content += block.get("text", "")

            mappings = parse_classification_response(text_content)

            for raw_name, mapped_value in mappings.items():
                if mapped_value == "JUNK":
                    conn.execute(
                        "INSERT OR IGNORE INTO effect_mappings "
                        "(raw_name, canonical_id, confidence, method) "
                        "VALUES (?, NULL, 0.0, 'llm_junk')",
                        (raw_name,),
                    )
                    stats["llm_junk"] += 1
                elif mapped_value in canonical_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO effect_mappings "
                        "(raw_name, canonical_id, confidence, method) "
                        "VALUES (?, ?, 0.85, 'llm_glm-4.7')",
                        (raw_name, canonical_ids[mapped_value]),
                    )
                    stats["llm_mapped"] += 1
                else:
                    logger.warning(
                        "LLM returned unknown canonical name '%s' for '%s'",
                        mapped_value,
                        raw_name,
                    )
                    stats["llm_failed"] += 1

            conn.commit()

        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.error("LLM classification batch failed: %s", exc)
            stats["llm_failed"] += len(batch)

        logger.info(
            "LLM batch %d-%d: %d mapped, %d junk, %d failed",
            i,
            i + len(batch),
            stats["llm_mapped"],
            stats["llm_junk"],
            stats["llm_failed"],
        )

    return stats
