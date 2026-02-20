"""Review effect extraction pipeline.

Reads Leafly user reviews from Strain Tracker DB, extracts effect mentions
via regex (+ optional LLM fallback), and imports aggregated effect reports
into the Cannalchemy DB with source="leafly-reviews".

Usage:
    python -m cannalchemy.data.review_pipeline \
        --db data/processed/cannalchemy.db \
        --st-db /srv/appdata/strain-tracker/strain-tracker.db \
        --limit 0 --llm-fallback
"""
import argparse
import json
import logging
import sqlite3
from pathlib import Path

from cannalchemy.data.confidence import compute_confidence_scores
from cannalchemy.data.consumer_import import import_effects_for_strain
from cannalchemy.data.consumer_mapper import build_effect_lookup, map_effect_name
from cannalchemy.data.review_extractor import (
    aggregate_strain_effects,
    extract_effects_llm,
    extract_effects_regex,
)
from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import CANONICAL_EFFECTS

logger = logging.getLogger(__name__)

SOURCE = "leafly-reviews"
DEFAULT_PROGRESS_FILE = Path(".leafly_reviews_progress.json")
LLM_BATCH_SIZE = 15


def load_reviews_by_strain(st_db_path: str) -> dict[str, list[str]]:
    """Load all external reviews from Strain Tracker DB grouped by strain name.

    Args:
        st_db_path: Path to Strain Tracker SQLite database.

    Returns:
        Dict mapping strain name -> list of review texts.
    """
    conn = sqlite3.connect(st_db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    rows = conn.execute(
        """
        SELECT s.name, er.review_text
        FROM external_reviews er
        JOIN strains s ON s.id = er.strain_id
        WHERE er.review_text IS NOT NULL AND length(er.review_text) > 10
        ORDER BY s.name
        """
    ).fetchall()
    conn.close()

    by_strain: dict[str, list[str]] = {}
    for name, text in rows:
        # Strip surrounding quotes from review texts
        text = text.strip().strip('"')
        if text:
            by_strain.setdefault(name, []).append(text)

    return by_strain


def build_name_mapping(conn: sqlite3.Connection) -> dict[str, int]:
    """Build case-insensitive strain name -> Cannalchemy strain ID mapping.

    Args:
        conn: Cannalchemy DB connection.

    Returns:
        Dict mapping lowercase strain name -> strain ID.
    """
    rows = conn.execute("SELECT id, name FROM strains").fetchall()
    mapping: dict[str, int] = {}
    for strain_id, name in rows:
        key = name.lower().strip()
        if key not in mapping:
            mapping[key] = strain_id
    return mapping


def _load_progress(progress_file: Path) -> set[str]:
    """Load set of already-processed strain names."""
    if progress_file.exists():
        try:
            data = json.loads(progress_file.read_text())
            return set(data.get("done", []))
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()


def _save_progress(progress_file: Path, done: set[str]) -> None:
    """Save set of processed strain names."""
    progress_file.write_text(json.dumps({"done": sorted(done)}))


def run_pipeline(
    db_path: str,
    st_db_path: str,
    limit: int = 0,
    llm_fallback: bool = False,
    progress_file: Path | None = None,
) -> dict:
    """Run the review extraction pipeline.

    Steps:
        1. Load reviews from ST DB grouped by strain name
        2. Build name -> strain_id mapping from Cannalchemy DB
        3. For each matched strain:
           a. Regex-extract effects from all reviews
           b. Optionally LLM-extract for strains with poor regex coverage
           c. Aggregate effect counts
           d. Map to canonical effects and import
        4. Recompute confidence scores

    Args:
        db_path: Path to Cannalchemy SQLite database.
        st_db_path: Path to Strain Tracker SQLite database.
        limit: Max strains to process (0 = all).
        llm_fallback: Use LLM for strains with poor regex coverage.

    Returns:
        Stats dict.
    """
    if progress_file is None:
        progress_file = DEFAULT_PROGRESS_FILE

    conn = init_db(db_path)
    lookup = build_effect_lookup(conn)

    stats = {
        "total_reviews": 0,
        "strains_with_reviews": 0,
        "strains_matched": 0,
        "strains_enriched": 0,
        "effects_imported": 0,
        "llm_calls": 0,
        "skipped_resumed": 0,
    }

    # Step 1: Load reviews
    logger.info("Loading reviews from Strain Tracker DB...")
    reviews_by_strain = load_reviews_by_strain(st_db_path)
    stats["strains_with_reviews"] = len(reviews_by_strain)
    stats["total_reviews"] = sum(len(v) for v in reviews_by_strain.values())
    logger.info(
        "Loaded %d reviews across %d strains",
        stats["total_reviews"],
        stats["strains_with_reviews"],
    )

    # Step 2: Build name mapping
    name_map = build_name_mapping(conn)
    logger.info("Built name mapping with %d Cannalchemy strains", len(name_map))

    # Step 3: Match and process
    done = _load_progress(progress_file)
    strain_names = sorted(reviews_by_strain.keys())
    if limit > 0:
        strain_names = strain_names[:limit]

    for i, strain_name in enumerate(strain_names):
        if strain_name in done:
            stats["skipped_resumed"] += 1
            continue

        # Match to Cannalchemy strain
        strain_id = name_map.get(strain_name.lower().strip())
        if strain_id is None:
            done.add(strain_name)
            continue

        stats["strains_matched"] += 1
        reviews = reviews_by_strain[strain_name]

        # Stage 1: Regex extraction
        extracted_reviews = []
        regex_empty_count = 0
        for text in reviews:
            effects = extract_effects_regex(text)
            total_found = sum(len(v) for v in effects.values())
            if total_found == 0:
                regex_empty_count += 1
            extracted_reviews.append({"text": text, "effects": effects})

        # Stage 2: Optional LLM fallback
        if llm_fallback and len(reviews) > 5 and regex_empty_count > len(reviews) * 0.7:
            cat_map = {e["name"]: e["category"] for e in CANONICAL_EFFECTS}
            # Collect indices and texts of empty reviews
            empty_indices = [
                j for j, r in enumerate(extracted_reviews)
                if sum(len(v) for v in r["effects"].values()) == 0
            ]
            empty_texts = [extracted_reviews[j]["text"] for j in empty_indices]

            # Process in batches
            all_llm_results = []
            for batch_start in range(0, len(empty_texts), LLM_BATCH_SIZE):
                batch = empty_texts[batch_start:batch_start + LLM_BATCH_SIZE]
                llm_results = extract_effects_llm(batch)
                all_llm_results.extend(llm_results)
                stats["llm_calls"] += 1

            # Merge LLM results back into extracted_reviews
            for k, idx in enumerate(empty_indices):
                if k < len(all_llm_results):
                    for name in all_llm_results[k]:
                        cat = cat_map.get(name, "positive")
                        if name not in extracted_reviews[idx]["effects"][cat]:
                            extracted_reviews[idx]["effects"][cat].append(name)

        # Aggregate
        aggregated = aggregate_strain_effects(extracted_reviews)

        if not aggregated:
            done.add(strain_name)
            continue

        # Map to canonical and import
        import_effects = []
        for effect_name, count in aggregated.items():
            mapped = map_effect_name(effect_name, lookup)
            if mapped:
                import_effects.append({
                    "canonical_id": mapped["canonical_id"],
                    "canonical_name": mapped["canonical_name"],
                    "votes": count,
                    "method": mapped["method"],
                })

        if import_effects:
            imported = import_effects_for_strain(conn, strain_id, import_effects, SOURCE)
            stats["effects_imported"] += imported
            if imported > 0:
                stats["strains_enriched"] += 1

        done.add(strain_name)

        # Progress save every 100 strains
        if (i + 1) % 100 == 0:
            _save_progress(progress_file, done)
            logger.info(
                "Progress: %d/%d strains | %d enriched | %d effects",
                i + 1, len(strain_names),
                stats["strains_enriched"], stats["effects_imported"],
            )

    # Final progress save
    _save_progress(progress_file, done)

    # Step 4: Recompute confidence scores
    logger.info("Recomputing confidence scores...")
    confidence_stats = compute_confidence_scores(conn)
    stats["confidence_updated"] = confidence_stats["updated"]

    conn.close()
    return stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract effects from Leafly reviews and import into Cannalchemy"
    )
    parser.add_argument("--db", required=True, help="Path to Cannalchemy SQLite DB")
    parser.add_argument("--st-db", required=True, help="Path to Strain Tracker SQLite DB")
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max strains to process (0 = all)",
    )
    parser.add_argument(
        "--llm-fallback", action="store_true",
        help="Use LLM for strains with poor regex coverage",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    stats = run_pipeline(args.db, args.st_db, args.limit, args.llm_fallback)

    print(f"\nReview Pipeline Complete:")
    print(f"  Total reviews:        {stats['total_reviews']}")
    print(f"  Strains with reviews: {stats['strains_with_reviews']}")
    print(f"  Strains matched:      {stats['strains_matched']}")
    print(f"  Strains enriched:     {stats['strains_enriched']}")
    print(f"  Effects imported:     {stats['effects_imported']}")
    print(f"  LLM calls:            {stats['llm_calls']}")
    print(f"  Skipped (resumed):    {stats['skipped_resumed']}")
    print(f"  Confidence updated:   {stats.get('confidence_updated', 0)}")


if __name__ == "__main__":
    main()
