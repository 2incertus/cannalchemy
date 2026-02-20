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

## Phase 1B: Cannlytics Lab Data Import (COMPLETE)

**Plan:** `docs/plans/2026-02-20-phase1b-cannlytics-import.md` (7 tasks)
**Commits:** 0c919ec → 377cb97 (7 commits)
**Tests:** 77 passing (26 new), 3 network-deselected

### Task-by-Task Results

| Task | Commit | Files | Tests | Status |
|------|--------|-------|-------|--------|
| 1. Value Cleaner & Config | 0c919ec | cannlytics_config.py, test | 11 new | DONE |
| 2. Download Pipeline | 42acc5f | cannlytics_download.py, test, pyproject.toml | 3 new | DONE |
| 3. Per-State Extractors | a34025f | cannlytics_extract.py, test | 4 new | DONE |
| 4. Lab Results Import | 3d5012e | cannlytics_import.py, test | 4 new | DONE |
| 5. Strain Cross-Reference | 6f6a08c | cannlytics_strain_match.py, test | 3 new | DONE |
| 6. Aggregation | e9b2ccb | cannlytics_aggregate.py, test | 3 new | DONE |
| 7. Live DB Import | 377cb97 | fixes to config/extract/match | 1 new (extract) | DONE |

### Plan vs Actual Results

| Metric | Plan Target | Actual | Notes |
|--------|-------------|--------|-------|
| States imported | 5 (NV,CA,MD,WA,MA) | **4** (NV,CA,MD,WA) | MA dropped: results 100% NaN, no strain names |
| Lab results | 200K+ | **1,394,000** | NV=994K, MD=185K, CA=134K, WA=82K |
| Compositions created | 200K+ | **285,645** | lab_tested, median aggregation |
| Strains enriched | — | **44,615** | 30K have lab terpene data |
| New strains | — | **42,624** | source='cannlytics' |
| Existing matched | — | **1,991** | Exact match to Strain Tracker |
| Total strains | 30K+ | **67,477** | 24,853 original + 42,624 new |
| New modules | 6 | **6** | config, download, extract, import, strain_match, aggregate |
| Tests | 65+ | **80** (77 run + 3 network) | 26 new from Phase 1B |

### Bugs Fixed During Execution

1. **MA data useless:** Results field 100% NaN, no product_name, only delta_9_thc flat. Removed from STATE_CONFIGS.
2. **WA Python dict notation:** Excel stores results as `[{'key': '9_thc', ...}]` (single quotes) not JSON. Added `ast.literal_eval` fallback in extractor.
3. **strain_type CHECK constraint:** Plan had `strain_type=''` but schema requires `('indica', 'sativa', 'hybrid', 'unknown')`. Fixed to `'unknown'`.
4. **Fuzzy matching too slow:** 42K names × 24K strains = O(1B) comparisons. Added `fuzzy=False` mode for exact-match-only + create new. Fuzzy matching deferred to post-processing.

### Architecture Decisions

1. **Import scope:** 4 states (not 5): NV, CA, MD, WA. MA dropped.
2. **Storage model:** lab_results → aggregate → strain_compositions.
3. **Strain matching:** Exact only for live import (fuzzy too slow at scale). Creates new strains.
4. **Aggregation:** Median per strain+molecule, tagged `measurement_type='lab_tested'`.
5. **Coexistence:** Both 'reported' (78K) and 'lab_tested' (286K) compositions kept.
6. **Dependencies added to pyproject.toml:** huggingface_hub>=0.20, openpyxl>=3.1.

### ML-Readiness After Phase 1B

- ML-ready strains: 4,603 / 65,953 = **7%** (down from 19% post-1A)
- Drop expected: denominator grew 3x from new Cannlytics strains with no effect reports
- Key metric: **30,553 strains now have lab-tested terpene data**
- Phase 1C (consumer data) will add effect reports to bring ML-readiness up

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
| cannlytics_config.py | Column mapping, value cleaning, state configs | 1B |
| cannlytics_download.py | HuggingFace dataset download | 1B |
| cannlytics_extract.py | Flat + JSON results extractors | 1B |
| cannlytics_import.py | Lab results chunked import | 1B |
| cannlytics_strain_match.py | Strain normalization + matching | 1B |
| cannlytics_aggregate.py | Median aggregation to compositions | 1B |

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
| test_cannlytics_config.py | 11 | 1B |
| test_cannlytics_download.py | 3 | 1B |
| test_cannlytics_extract.py | 5 | 1B |
| test_cannlytics_import.py | 4 | 1B |
| test_cannlytics_strain_match.py | 3 | 1B |
| test_cannlytics_aggregate.py | 3 | 1B |
| **Total** | **80 (77 run + 3 network)** | |

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
networkx, rapidfuzz, httpx, pandas, sqlalchemy, huggingface_hub, openpyxl
# dev: pytest
```

## Z.AI API

- Endpoint: `https://api.z.ai/api/anthropic/v1/messages`
- Model: `glm-4.7`
- API key: stored in `~/config/n8n.env` as `ZAI_API_KEY`
- Used for: LLM effect classification (Phase 1A Task 3)
