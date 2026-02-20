"""Consumer effect data pipeline orchestrator.

Coordinates scraping effect data from AllBud/Leafly for strains that have
chemical compositions but no effect reports, maps to canonical effects,
imports into the database, and computes confidence scores.
"""
import argparse
import json
import logging
import sqlite3
import time
from pathlib import Path

import httpx

from cannalchemy.data.allbud_scraper import parse_allbud_page
from cannalchemy.data.confidence import compute_confidence_scores
from cannalchemy.data.consumer_config import (
    SCRAPE_CONFIG,
    strain_to_allbud_url,
    strain_to_leafly_url,
)
from cannalchemy.data.consumer_import import import_effects_for_strain
from cannalchemy.data.consumer_mapper import build_effect_lookup, map_effects_batch
from cannalchemy.data.leafly_scraper import parse_leafly_markdown, parse_next_data
from cannalchemy.data.schema import init_db

logger = logging.getLogger(__name__)


def get_priority_strains(conn: sqlite3.Connection) -> list[dict]:
    """Get strains that have compositions but no effect reports.

    These are the highest-priority targets for consumer effect scraping:
    they have chemical data (terpenes/cannabinoids) but lack the effect
    labels needed for ML training.

    Ordering prefers strain-tracker source strains first, then alphabetical.

    Args:
        conn: SQLite database connection.

    Returns:
        List of dicts with keys: id, name, strain_type, source.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT s.id, s.name, s.strain_type, s.source
        FROM strains s
        INNER JOIN strain_compositions sc ON s.id = sc.strain_id
        LEFT JOIN effect_reports er ON s.id = er.strain_id
        WHERE er.id IS NULL
        ORDER BY
            CASE WHEN s.source = 'strain-tracker' THEN 0 ELSE 1 END,
            s.name
        """
    ).fetchall()

    return [
        {"id": row[0], "name": row[1], "strain_type": row[2], "source": row[3]}
        for row in rows
    ]


def _scrape_strain(strain: dict, source: str) -> dict | None:
    """Scrape effect data for a single strain from the specified source.

    For AllBud: direct httpx GET, parse HTML with parse_allbud_page.
    For Leafly: try direct httpx GET with parse_next_data, fall back to
    Firecrawl API with parse_leafly_markdown.

    Args:
        strain: Dict with id, name, strain_type, source.
        source: "allbud" or "leafly".

    Returns:
        Dict with "effects" list (name strings) and optionally "votes" dict,
        or None if scraping failed.
    """
    timeout = SCRAPE_CONFIG["timeout"]
    headers = {"User-Agent": SCRAPE_CONFIG["user_agent"]}

    if source == "allbud":
        url = strain_to_allbud_url(strain["name"], strain["strain_type"])
        try:
            resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if resp.status_code != 200:
                logger.warning("AllBud %s returned %d", url, resp.status_code)
                return None
            result = parse_allbud_page(resp.text)
            all_effects = result.effects + result.medical + result.negatives
            if not all_effects:
                logger.info("No effects found for %s on AllBud", strain["name"])
                return None
            return {"effects": all_effects, "votes": {}}
        except httpx.HTTPError as e:
            logger.error("AllBud request failed for %s: %s", strain["name"], e)
            return None

    elif source == "leafly":
        url = strain_to_leafly_url(strain["name"])

        # Strategy 1: Direct httpx GET with __NEXT_DATA__ parsing
        try:
            resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if resp.status_code == 200:
                next_data = parse_next_data(resp.text)
                if next_data:
                    # Extract effects from the JSON data
                    effects_list = []
                    votes_map = {}
                    for effect in next_data.get("effects", []):
                        name = effect.get("name", "")
                        if name:
                            effects_list.append(name)
                            votes_map[name] = effect.get("votes", 0)
                    if effects_list:
                        return {"effects": effects_list, "votes": votes_map}
        except httpx.HTTPError as e:
            logger.warning("Leafly direct request failed for %s: %s", strain["name"], e)

        # Strategy 2: Fall back to Firecrawl API
        try:
            firecrawl_url = f"{SCRAPE_CONFIG['firecrawl_api_url']}/scrape"
            firecrawl_resp = httpx.post(
                firecrawl_url,
                json={"url": url, "formats": ["markdown"]},
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            if firecrawl_resp.status_code == 200:
                data = firecrawl_resp.json()
                markdown = data.get("data", {}).get("markdown", "")
                if markdown:
                    result = parse_leafly_markdown(markdown)
                    all_effects = (
                        [e["name"] for e in result.effects]
                        + [m["name"] for m in result.medical]
                        + result.negatives
                    )
                    votes_map = {e["name"]: e["votes"] for e in result.effects}
                    if all_effects:
                        return {"effects": all_effects, "votes": votes_map}
        except httpx.HTTPError as e:
            logger.error("Firecrawl request failed for %s: %s", strain["name"], e)

        return None

    else:
        logger.error("Unknown source: %s", source)
        return None


def _load_progress(source: str) -> set:
    """Load progress file for resumability.

    Args:
        source: "allbud" or "leafly".

    Returns:
        Set of strain IDs already processed.
    """
    progress_file = Path(f".{source}_progress.json")
    if progress_file.exists():
        try:
            data = json.loads(progress_file.read_text())
            return set(data.get("done_ids", []))
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()


def _save_progress(source: str, done_ids: set) -> None:
    """Save progress file for resumability.

    Args:
        source: "allbud" or "leafly".
        done_ids: Set of strain IDs already processed.
    """
    progress_file = Path(f".{source}_progress.json")
    progress_file.write_text(json.dumps({"done_ids": sorted(done_ids)}))


def run_pipeline(db_path: str, source: str = "allbud", limit: int = 0) -> dict:
    """Run the consumer effect scraping pipeline.

    Steps:
    1. Connect to DB
    2. Get priority strains (apply limit if set)
    3. Build effect lookup
    4. Load progress file for resumability
    5. For each strain: scrape, map effects, import, save progress
    6. Compute confidence scores
    7. Return stats

    Args:
        db_path: Path to SQLite database.
        source: "allbud" or "leafly".
        limit: Max strains to process (0 = all).

    Returns:
        Stats dict with keys: total, scraped, mapped, imported, skipped, errors.
    """
    conn = init_db(db_path)
    strains = get_priority_strains(conn)

    if limit > 0:
        strains = strains[:limit]

    lookup = build_effect_lookup(conn)
    done_ids = _load_progress(source)

    stats = {
        "total": len(strains),
        "scraped": 0,
        "mapped": 0,
        "imported": 0,
        "skipped": 0,
        "errors": 0,
    }

    save_interval = SCRAPE_CONFIG.get("batch_size", 100)

    for i, strain in enumerate(strains):
        if strain["id"] in done_ids:
            stats["skipped"] += 1
            continue

        # Scrape
        scraped = _scrape_strain(strain, source)
        if scraped is None:
            stats["errors"] += 1
            done_ids.add(strain["id"])
            continue

        stats["scraped"] += 1

        # Map effects to canonical
        map_result = map_effects_batch(scraped["effects"], lookup)
        mapped_effects = map_result["mapped"]

        if not mapped_effects:
            logger.info("No mappable effects for %s", strain["name"])
            done_ids.add(strain["id"])
            continue

        stats["mapped"] += len(mapped_effects)

        # Build import-ready effect list
        import_effects = []
        votes_map = scraped.get("votes", {})
        for m in mapped_effects:
            import_effects.append({
                "canonical_id": m["canonical_id"],
                "canonical_name": m["canonical_name"],
                "votes": votes_map.get(m["original_name"], 0),
                "method": m["method"],
            })

        # Import to DB
        count = import_effects_for_strain(conn, strain["id"], import_effects, source)
        stats["imported"] += count

        done_ids.add(strain["id"])

        # Save progress periodically
        if (i + 1) % save_interval == 0:
            _save_progress(source, done_ids)
            logger.info("Progress: %d/%d strains processed", i + 1, len(strains))

        # Rate limit
        time.sleep(SCRAPE_CONFIG["rate_limit"])

    # Final progress save
    _save_progress(source, done_ids)

    # Compute confidence scores
    confidence_stats = compute_confidence_scores(conn)
    stats["confidence_updated"] = confidence_stats["updated"]

    conn.close()
    return stats


def main():
    """CLI entry point for the consumer pipeline."""
    parser = argparse.ArgumentParser(
        description="Scrape consumer effect data and import into Cannalchemy DB"
    )
    parser.add_argument(
        "--db", required=True, help="Path to SQLite database"
    )
    parser.add_argument(
        "--source",
        choices=["allbud", "leafly"],
        default="allbud",
        help="Source site to scrape (default: allbud)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max strains to process (0 = all, default: 0)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    stats = run_pipeline(args.db, args.source, args.limit)
    print(f"\nPipeline complete:")
    print(f"  Total strains:      {stats['total']}")
    print(f"  Scraped:            {stats['scraped']}")
    print(f"  Effects mapped:     {stats['mapped']}")
    print(f"  Effects imported:   {stats['imported']}")
    print(f"  Skipped (resumed):  {stats['skipped']}")
    print(f"  Errors:             {stats['errors']}")
    print(f"  Confidence updated: {stats.get('confidence_updated', 0)}")


if __name__ == "__main__":
    main()
