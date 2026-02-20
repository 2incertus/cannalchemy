"""Data cleaning pipeline orchestrator for Phase 1A."""
import sqlite3
from dataclasses import dataclass

from cannalchemy.data.taxonomy import seed_canonical_effects
from cannalchemy.data.llm_classify import classify_effects_rule_based, classify_effects_llm
from cannalchemy.data.expand_molecules import expand_cannabinoids
from cannalchemy.data.dedup_strains import run_deduplication


@dataclass
class CleaningConfig:
    skip_llm: bool = False
    skip_dedup: bool = False
    llm_api_key: str = ""
    dedup_threshold: int = 90


def run_cleaning_pipeline(conn: sqlite3.Connection, config: CleaningConfig) -> dict:
    """Run the full Phase 1A cleaning pipeline.

    Steps:
    1. Seed canonical effects taxonomy
    2. Expand molecules (add CBN, CBG, CBC, THCV + bindings)
    3. Rule-based effect classification (exact + synonym matching)
    4. LLM effect classification (if enabled)
    5. Strain deduplication (if enabled)
    6. Purge null effect reports
    """
    stats = {}

    # 1. Seed canonical effects
    count = seed_canonical_effects(conn)
    stats["canonical_effects_seeded"] = count

    # 2. Expand molecules
    mol_stats = expand_cannabinoids(conn)
    stats.update(mol_stats)

    # 3. Rule-based classification
    rule_stats = classify_effects_rule_based(conn)
    stats["rule_based"] = rule_stats

    # 4. LLM classification (if enabled)
    if not config.skip_llm and config.llm_api_key:
        llm_stats = classify_effects_llm(conn, config.llm_api_key)
        stats["llm"] = llm_stats

    # 5. Strain deduplication
    if not config.skip_dedup:
        dedup_stats = run_deduplication(conn, threshold=config.dedup_threshold)
        stats["dedup"] = dedup_stats

    # 6. Purge null effect reports
    deleted = conn.execute(
        "DELETE FROM effect_reports WHERE effect_id IN "
        "(SELECT id FROM effects WHERE name = 'null')"
    ).rowcount
    conn.commit()
    stats["null_reports_purged"] = deleted

    # 7. Summary
    mapped = conn.execute("SELECT COUNT(*) FROM effect_mappings WHERE canonical_id IS NOT NULL").fetchone()[0]
    junk = conn.execute("SELECT COUNT(*) FROM effect_mappings WHERE canonical_id IS NULL").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM effects").fetchone()[0]
    stats["summary"] = {
        "total_raw_effects": total,
        "mapped_to_canonical": mapped,
        "classified_as_junk": junk,
        "still_unmapped": total - mapped - junk,
    }

    return stats
