# Cannalchemy Session Log

> Tracks all implementation decisions, progress, and deviations across sessions. Review this at the start of every new session.

---

## Project Overview

- **Repo:** https://github.com/2incertus/cannalchemy
- **Local:** ~/cannalchemy
- **Venv:** ~/cannalchemy/.venv (Python 3.12)
- **Live DB:** ~/cannalchemy/data/processed/cannalchemy.db (NOT in git, .gitignore'd)
- **Source DB:** /srv/appdata/strain-tracker/strain-tracker.db (25K strains)

---

## Phase 1: Data Foundation (COMPLETE)

**Commits:** 067ae14 → 748f2d1 (8 commits)
**Tests:** 24 passing, 3 network-deselected

Built the core data layer:
- SQLite schema (9 tables), strain import (24,853 strains), PubChem client (27 compounds), ChEMBL client (6 receptors, 14/19 bindings), NetworkX knowledge graph, data pipeline CLI, exploratory notebook.

### Key bugs fixed in Phase 1:
- **O.G. Kush normalization:** periods must be REMOVED not replaced with space (`name.replace('.', '')`)
- **INSERT OR IGNORE + lastrowid:** `lastrowid` retains previous value on IGNORE — must use `cur.rowcount == 1` instead

---

## Phase 1A: Data Cleaning (COMPLETE)

**Plan:** `docs/plans/2026-02-20-phase1a-data-cleaning.md`
**Commits:** fc21bab → 9adb6a5 (6 commits)
**Tests:** 48 passing (24 new), 3 network-deselected

### Task-by-Task Results

| Task | Commit | Files | Tests | Status |
|------|--------|-------|-------|--------|
| 1. Schema Migration | fc21bab | schema.py modified, test_schema_v2.py created | 3 new | DONE |
| 2. Canonical Taxonomy | 40908b9 | taxonomy.py created, test_taxonomy.py created | 7 new | DONE |
| 3. LLM Classification | 5b6d7ec | llm_classify.py created, test_llm_classify.py created | 5 new | DONE |
| 4. Expand Molecules | 958dd30 | expand_molecules.py created, test_expand_molecules.py created | 4 new | DONE |
| 5. Strain Dedup | c3763e8 | dedup_strains.py created, test_dedup_strains.py created | 3 new | DONE |
| 6. Cleaning Pipeline | 9adb6a5 | cleaning.py created, test_cleaning.py created | 2 new | DONE |
| 7. Run on Live DB | (operational, no commit) | — | — | DONE |

### Plan vs Actual Results

| Metric | Plan Target | Actual | Notes |
|--------|-------------|--------|-------|
| Canonical effects | 60+ | **51** | 20 positive + 12 negative + 19 medical. Slightly under target but each is pharmacology-grounded. |
| Effect mappings | 2,179 (all classified) | **2,199** (all classified) | 20 extra from LLM discovering sub-classifications |
| Mapped to canonical | — | **532** | 26 exact + 24 synonym + 482 LLM |
| Classified as junk | — | **1,667** | 1,035 length filter + 622 LLM junk + 10 manual |
| Still unmapped | 0 | **0** | 100% classification rate |
| Null reports purged | 8,434 | **8,434** | Exact match |
| Cannabinoids | 6 | **6** | THC, CBD, CBN, CBG, CBC, THCV |
| Binding affinities | 19 | **19** | All 19/19 seeded |
| Strain aliases | TBD | **1,524** | 1,260 clusters at threshold=92 |
| New tables | 3 | **3** | canonical_effects, effect_mappings, strain_aliases |
| Tests | 45+ | **51** (48 run, 3 network) | Exceeded target |

### Decisions Made During Implementation

1. **Canonical effects count:** 51 instead of 60+. We chose quality over quantity — each effect has a real pharmacology grounding with receptor_pathway. The plan's "60-80" range included potential duplicates.

2. **LLM classification model:** Used GLM-4.7 via Z.AI API (Anthropic-compatible). Cost was minimal. One batch of 40 failed with 502 — retried successfully, remaining 10 were obvious junk classified manually.

3. **Dedup threshold:** Used 92 (not 90) for first pass as the plan suggested being conservative. Found 1,260 clusters / 1,524 aliases. Unique strains: 23,329 (from 24,853).

4. **Live DB migration:** The existing DB was created with v1 schema. Applied ALTER TABLE + CREATE TABLE migration manually before running the pipeline. Future sessions should note that `init_db()` creates v2 schema for new DBs, but existing DBs need migration.

5. **ML-readiness after 1A:** 4,523 / 23,329 = **19%** — below the current 25% (6,211 / 24,853) because dedup removed some strains from the denominator. The absolute count also dropped because many effect reports were for "null" effects that got purged. This is expected — 1A was about cleaning, not expanding. Phases 1B and 1C will expand the dataset.

6. **Classification method breakdown:**
   - length_filter: 1,035 (strings >40 chars → auto-junk)
   - llm_junk: 622 (LLM confirmed as junk)
   - llm_glm-4.7: 482 (LLM classified to canonical)
   - exact_match: 26 (exact canonical name match)
   - synonym_match: 24 (synonym lookup match)
   - manual_junk: 10 (unicode garbage, manually classified)

---

## Phase 1B: Cannlytics Lab Data Import (IN PROGRESS)

**Plan:** `docs/plans/2026-02-20-phase1b-cannlytics-import.md` (7 tasks)
**Design doc:** `docs/plans/2026-02-20-dataset-enrichment-design.md` (Section: Sub-phase 1B)
**Status:** Implementation plan written, execution starting

### Architecture Decisions (from interview)

1. **Import scope:** Top 5 states + California → revised to NV, CA, MD, WA, MA (608K records). Skipping OR (no terpenes, no strain names) and MI (13 cols, useless).
2. **Storage model:** Import into `lab_results` table only, aggregate separately into `strain_compositions`.
3. **Unmatched strains:** Create new strains with `source='cannlytics'`.
4. **Aggregation method:** Median per strain+molecule pair.
5. **Data coexistence:** Keep both `measurement_type='reported'` (Strain Tracker) and `measurement_type='lab_tested'` (Cannlytics) in `strain_compositions`.
6. **Molecule scope:** Map to existing 27 molecules only (no new ones).

### Data Exploration Findings

Schema varies **dramatically** per state:

| State | Records | Strain Name | Terpene Data | Format | Priority |
|-------|---------|-------------|--------------|--------|----------|
| NV | 153K | product_name | Flat columns (88%, 13 terpenes) | CSV | HIGH |
| CA | 72K | strain_name (sparse) + product_name | JSON results (157 analytes) | CSV | HIGH |
| MD | 105K | strain_name (100%) | Only total_terpenes | CSV | MEDIUM |
| WA | 203K | strain_name (84%) | JSON results (sparse terpenes) | XLSX | MEDIUM |
| MA | 75K | No strain_name | JSON results (TBD) | CSV | MEDIUM |
| OR | 197K | No strain_name | Only THC/CBD flat | CSV | SKIP |
| MI | 90K | No strain_name | 13 cols total | CSV | SKIP |

Key technical issues:
- Column names vary: `d_limonene` vs `limonene`, `alpha_ocimene` vs `ocimene`
- Values can be: floats, "ND", "<LLOQ", sentinel values (1e-9, 1e-7)
- NV uses flat columns; CA/WA/MA use nested JSON `results` field
- WA uses .xlsx (requires openpyxl), rest are .csv

### Dependencies Added (not yet in pyproject.toml)
- `huggingface_hub` — HuggingFace dataset download
- `pandas` — CSV/XLSX reading and data manipulation
- `pyarrow` — Parquet support (pandas optional dep)
- `openpyxl` — Excel .xlsx support for WA data

**Target:** 200K+ lab-tested compositions, median 8-12 terpenes per strain

---

## Phase 1C: Consumer Data (Leafly + AllBud)

**Plan:** `docs/plans/2026-02-20-dataset-enrichment-design.md` (Section: Sub-phase 1C)
**Status:** Design approved, implementation plan NOT yet written

**What it does:**
- Scrape Leafly and AllBud strain pages for effect reports
- Multi-source merge with confidence scoring
- Expand effect reports to 100K+
- Skip Reddit (too noisy)

**Target:** 15,000+ ML-ready strains (60%+)

---

## Phase 2: Effect Prediction (NOT STARTED)

**What it does:**
- XGBoost model: terpene/cannabinoid profile → predicted effects
- Requires Phase 1A-1C data enrichment first

---

## File Inventory

### Source modules (`cannalchemy/data/`)
| File | Purpose | Phase |
|------|---------|-------|
| schema.py | SQLite schema v2 (12 tables) | 1 + 1A |
| normalize.py | Strain name normalization | 1 |
| strain_import.py | Import from Strain Tracker | 1 |
| pubchem.py | PubChem API + 27 cached compounds | 1 |
| chembl.py | ChEMBL API + 6 receptors + 19 bindings | 1 |
| graph.py | NetworkX knowledge graph | 1 |
| pipeline.py | Phase 1 pipeline orchestrator + CLI | 1 |
| taxonomy.py | 51 canonical effects with pharmacology | 1A |
| llm_classify.py | Rule-based + LLM effect classification | 1A |
| expand_molecules.py | Add CBN, CBG, CBC, THCV + bindings | 1A |
| dedup_strains.py | Fuzzy strain deduplication | 1A |
| cleaning.py | Phase 1A cleaning orchestrator | 1A |

### Test files (`tests/`)
| File | Tests | Phase |
|------|-------|-------|
| test_schema.py | 3 | 1 |
| test_schema_v2.py | 3 | 1A |
| test_normalize.py | 6 | 1 |
| test_strain_import.py | 4 | 1 |
| test_pubchem.py | 4 (2 network) | 1 |
| test_chembl.py | 4 (1 network) | 1 |
| test_graph.py | 4 | 1 |
| test_pipeline.py | 2 | 1 |
| test_taxonomy.py | 7 | 1A |
| test_llm_classify.py | 5 | 1A |
| test_expand_molecules.py | 4 | 1A |
| test_dedup_strains.py | 3 | 1A |
| test_cleaning.py | 2 | 1A |
| **Total** | **51 (48 run + 3 network)** | |

### Docs
| File | Purpose |
|------|---------|
| docs/plans/2026-02-20-cannalchemy-design.md | Original system design |
| docs/plans/2026-02-20-cannalchemy-phase1-plan.md | Phase 1 implementation plan |
| docs/plans/2026-02-20-dataset-enrichment-design.md | 1A/1B/1C enrichment design (approved) |
| docs/plans/2026-02-20-phase1a-data-cleaning.md | Phase 1A implementation plan (7 tasks) |
| docs/plans/2026-02-20-phase1b-cannlytics-import.md | Phase 1B implementation plan (7 tasks) |
| docs/SESSION-LOG.md | This file — cross-session tracking |

---

## Dependencies

```
# pyproject.toml
networkx, rapidfuzz, httpx, requests
# Phase 1B additions (installed, not yet in pyproject.toml):
huggingface_hub, pandas, pyarrow, openpyxl
# dev: pytest
```

## Z.AI API

- Endpoint: `https://api.z.ai/api/anthropic/v1/messages`
- Model: `glm-4.7`
- API key: stored in `~/config/n8n.env` as `ZAI_API_KEY`
- Used for: LLM effect classification (Phase 1A Task 3)
