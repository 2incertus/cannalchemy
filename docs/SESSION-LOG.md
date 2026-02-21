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

## Phase 1C: Consumer Data (Leafly + AllBud) — COMPLETE

**Plan:** `docs/plans/2026-02-20-phase1c-consumer-data.md` (7 tasks)
**Commits:** bead366 → e45a79f (6 commits, Tasks 1-6), + Phase 1C.2 (uncommitted)
**Tests:** 144 passing (67 new), 3 network-deselected
**Status:** All tasks COMPLETE including live DB import

### Task-by-Task Results

| Task | Commit | Files | Tests | Status |
|------|--------|-------|-------|--------|
| 1. Consumer Config & URL Builder | bead366 | consumer_config.py, test | 7 new | DONE |
| 2. AllBud Scraper | 3f96837 | allbud_scraper.py, test, fixture | 11 new | DONE |
| 3. Leafly Scraper | 00dd570 | leafly_scraper.py, test, fixture | 8 new | DONE |
| 4. Consumer Effect Mapper | 7eb9212 | consumer_mapper.py, test | 8 new | DONE |
| 5. Consumer Data Importer | 712dae2 | consumer_import.py, test | 5 new | DONE |
| 6. Confidence + Pipeline CLI | e45a79f | confidence.py, consumer_pipeline.py, tests | 6 new | DONE |
| 7. Run on Live DB | (operational) | — | — | DONE |

### Phase 1C.2: Leafly Review Effect Extraction

| Task | Files | Tests | Status |
|------|-------|-------|--------|
| Firecrawl Key Config | consumer_config.py (modified) | — | DONE |
| Review Effect Extractor | review_extractor.py (new) | 14 new | DONE |
| Review Import Pipeline | review_pipeline.py (new) | 8 new | DONE |
| Run on Live DBs | (operational) | — | DONE |

**Results:**
- 165,146 reviews processed across 2,524 strains (from Strain Tracker `external_reviews`)
- 2,499 strains matched to Cannalchemy DB (99% match rate)
- **2,379 strains enriched** with effect data
- **39,583 effect_reports imported** with source="leafly-reviews"
- 0 LLM calls needed (regex extraction alone was highly effective)
- 2,156 strains now have multi-source effect confirmation
- Pipeline completed in ~2 minutes

### Architecture

- **AllBud scraper:** httpx + BeautifulSoup, parses flip-card panels (Effects, May Relieve, Flavors)
- **Leafly scraper:** Firecrawl API → markdown, regex parsing for effects+votes, medical+percentages, terpenes
- **Review extractor:** regex matching against 52 canonical effects + all synonyms from review text, with optional LLM fallback via Z.AI
- **Consumer mapper:** normalize → exact match → synonym match → fuzzy match (≥85) → unmapped
- **Pipeline CLIs:**
  - `python -m cannalchemy.data.consumer_pipeline --db DB --source allbud|leafly --limit N`
  - `python -m cannalchemy.data.review_pipeline --db DB --st-db ST_DB --limit N --llm-fallback`
- **Confidence scoring:** base 0.4 + source bonus (+0.2/source) + vote bonus (0-0.2 log scale), max 1.0
- **Resumability:** JSON checkpoint files per pipeline

### Decisions Made

1. **beautifulsoup4 added** as dependency (AllBud HTML parsing)
2. **taxonomy.py updated:** added "lack-of-appetite" as 52nd canonical effect (distinct from medical "appetite-loss")
3. **AllBud URL includes strain type** (indica/sativa/hybrid) — follows redirects if wrong
4. **Firecrawl markdown preferred** over JSON extraction (1 credit vs 5 credits per page)
5. **Effect mapping is near-1:1** — Leafly/AllBud names map directly after lowercase+hyphenation
6. **Review extraction via regex only** — 52 canonical effects + all synonyms matched as whole words, case-insensitive. LLM fallback available but unnecessary (regex coverage was sufficient)
7. **Firecrawl API key** loaded from env var or Strain Tracker `.env` file (fallback path)

### Combined Live DB Import Results

| Source | Effect Reports | Strains Enriched |
|--------|---------------|-----------------|
| strain-tracker | 24,624 | 6,614 |
| leafly-reviews | 39,583 | 2,389 |
| allbud | 3,793 | 389 |
| **Total** | **68,000** | **~7,000 unique** |

### ML-Readiness After Phase 1C

- ML-ready strains (pre-cleanup): 6,073 / 67,477 = 9.0%
- Bottleneck: 42K Cannlytics strains have compositions but no effect data (they don't exist in Leafly review corpus)
- Top effects from reviews: relaxed (28K mentions), pain (17K), anxious (12K), happy (11K), energetic (10K)

### Effect Label Cleanup (post-1C.2)

Cleaned strain-tracker effect labels:
- **36 synonym effects remapped** to canonical (e.g., "relaxing"→"relaxed", "uplifting"→"uplifted"): 2,215 reports saved
- **13 duplicate reports merged** (same strain+effect+source after remap)
- **2,966 true junk reports deleted** (sentence fragments, non-effect strings)
- **2,153 orphaned effect entries removed** from effects table
- Effects table now has exactly **51 entries** (all canonical)
- Confidence scores recomputed for 66,112 reports

### Final Phase 1 ML-Readiness

| Metric | Value |
|--------|-------|
| ML-ready strains | **4,980** / 67,477 (7.4%) |
| Effect reports | 66,112 (all canonical) |
| Effects table | 51 entries (clean) |
| Multi-source strains | 2,188 |
| Sources | strain-tracker (21,645), leafly-reviews (39,583), allbud (4,856) |

---

## Phase 2: Effect Prediction — COMPLETE

**Goal:** XGBoost ensemble predicting effects from terpene/cannabinoid profiles
**Data:** 5,017 ML-ready strains, 27 molecules + 8 engineered features = 35 total
**Compute:** N100 mini-PC (CPU-only, ~6 min training)

### Task-by-Task Results

| Task | Files | Tests | Status |
|------|-------|-------|--------|
| Dataset Builder | dataset.py (new) | 15 new | DONE |
| Effect Predictor | effect_predictor.py (new) | 12 new | DONE |
| Model Improvement (v2) | dataset.py (engineered features) | — | DONE |
| Prediction API | api/app.py (new) | 8 new | DONE |

### Model Performance

**V1 (raw 27 features):** Mean AUC = 0.802, Median = 0.814
**V2 (35 features with engineering):** Mean AUC = **0.811**, Median = **0.818**

#### Engineered Features (v2)
- `is_indica`, `is_sativa`, `is_hybrid` — strain type one-hot
- `total_terpenes`, `total_cannabinoids` — aggregate concentrations
- `terpene_diversity` — count of non-zero terpenes
- `dominant_terpene_pct` — max terpene value
- `thc_cbd_ratio` — THC/CBD ratio

#### Weak Effect Improvement (v1 → v2)

| Effect | v1 AUC | v2 AUC | Delta |
|--------|--------|--------|-------|
| creative | 0.666 | 0.672 | +0.006 |
| uplifted | 0.685 | 0.695 | +0.010 |
| relaxed | 0.705 | 0.712 | +0.007 |
| euphoric | 0.723 | 0.727 | +0.005 |
| energetic | 0.755 | 0.768 | +0.013 |
| inflammation | 0.712 | 0.754 | +0.042 |
| fatigue-medical | 0.760 | 0.799 | +0.038 |

#### Top 10 Effects by AUC (v2)

| Effect | AUC | F1 | Category |
|--------|-----|-----|----------|
| pain | 0.872 | 0.711 | medical |
| anxious | 0.865 | 0.665 | negative |
| anxiety | 0.863 | 0.657 | medical |
| depression | 0.862 | 0.630 | medical |
| stress | 0.860 | 0.661 | medical |
| body-high | 0.856 | 0.626 | positive |
| insomnia | 0.853 | 0.563 | medical |
| head-high | 0.850 | 0.635 | positive |
| spacey | 0.842 | 0.441 | positive |
| couch-lock | 0.838 | 0.564 | negative |

### Feature Importance Analysis

**Dominant terpene predictors across all effects:**

| Terpene | Top predictor for | Notes |
|---------|-------------------|-------|
| **Ocimene** | pain, anxiety, stress, depression, body-high, tingly, happy, giggly, headache, talkative | Most powerful predictor overall; drives medical + mood effects |
| **Pinene** | focused (0.28), hungry (0.35), nauseous, paranoid, sleepy, couch-lock, migraines, adhd, nausea-relief | Strong discriminator for cognitive + appetite effects |
| **Humulene** | fatigued, ptsd, dizzy, dry-eyes, meditative, bipolar, fibromyalgia | Anti-inflammatory terpene; predicts sedative/medical effects |
| **Linalool** | calm (0.22), relaxed (0.18), sleepy, insomnia, fibromyalgia | Known anxiolytic; matches pharmacology |

**Engineered features that mattered:**
- `terpene_diversity` — top-3 for creative (0.094); diverse profiles → creative effects
- `is_sativa` — top-3 for creative (0.067), energetic; strain genetics matter
- `total_cannabinoids` — useful for medical predictions (pain, anxiety)
- `thc_cbd_ratio` — contributes to anxious/paranoid/headache predictions

**Pharmacological validation:**
- Linalool → calm/relaxed/sleepy — matches known GABAergic/anxiolytic activity
- Pinene → focused — matches known acetylcholinesterase inhibition
- Ocimene → pain/anti-inflammatory — matches known anti-inflammatory properties
- Humulene → fatigue/sedation — matches known sedative properties

### Prediction API

**Endpoints:**
- `POST /predict` — takes chemical profile, returns ranked effect predictions with probabilities
- `GET /effects` — lists all 51 predictable effects with AUC scores
- `GET /features` — lists expected input features
- `GET /health` — health check

**Example:** Blue Dream profile (THC 21%, myrcene 0.74%, pinene 0.42%) → relaxed 84%, happy 80%, pain 79%, focused 77%

---

## Phase 3: Visualization + UI — COMPLETE

**Plan:** `docs/plans/2026-02-20-phase3-implementation.md` (14 tasks)
**Commits:** 8398874 → 9868de2 (9 commits on `worktree-phase3-ui` branch)
**E2E Tests:** 24 passing (Playwright, Chromium)
**Design:** "The Apothecary Lab" — dark botanical science aesthetic

### Stack

- **Frontend:** React 19, Vite 7, Tailwind CSS v4, D3.js 7, Recharts 3
- **Backend:** FastAPI with XGBoost prediction cache
- **Docker:** Multi-stage build (Node.js → Python + nginx + supervisord)
- **Port:** 8422 (maps to 8080 inside container)

### Pages Built (6)

| Page | Route | Key Features |
|------|-------|-------------|
| Landing | `/` | Animated SVG radar, feature cards with IntersectionObserver, live stats |
| Explorer | `/explore` | Effect picker with categories, type filters, strain cards, match search |
| Strain Detail | `/strain/:name` | Terpene radar, effect bars, pathway diagram (D3 force-directed) |
| Compare | `/compare` | Side-by-side strain comparison with overlaid radars |
| Knowledge Graph | `/graph` | Interactive D3 force-directed graph, node detail panel |
| Data Quality | `/quality` | Bar charts for AUC, effect distribution, data sources |

### Components Built (8)

| Component | Purpose |
|-----------|---------|
| TerpeneRadar | SVG radar chart with animated data polygons |
| EffectBars | Horizontal probability bars with category colors |
| StrainCard | Card with type badge, compositions, top effects |
| EffectChip | Toggle buttons for effect selection (positive/negative/medical) |
| TypeBadge | Colored pill for indica/sativa/hybrid |
| PathwayDiagram | D3 force-directed molecule→receptor pathway graph |
| HeroRadar | Landing page animated radar with pulsing effects |
| Navbar | Fixed nav with active state highlighting |

### API Endpoints Added (Phase 3)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/strains` | GET | Search/list strains with compositions |
| `/strains/{name}` | GET | Full strain profile + predictions + pathways |
| `/match` | POST | Find strains matching desired effects |
| `/graph` | GET | Knowledge graph nodes and edges |
| `/graph/{node_id}` | GET | Subgraph centered on a node |
| `/stats` | GET | Data quality statistics |

### Performance Optimizations

- **Prediction cache:** Pre-computes all ML predictions at startup in background thread
- **threading.Event:** Match endpoint waits for cache instead of double-building
- **Single JOIN query:** Eliminated N+1 queries for strain compositions
- **Batch prediction:** XGBoost predicts 6,553 strains in one `predict_proba` call
- **Result:** Match endpoint responds in <50ms after cache warm (was 5+ min timeout)

### Docker Deployment

- Multi-stage Dockerfile: `node:22-alpine` (frontend) → `python:3.12-slim` (API + nginx)
- supervisord runs uvicorn (8421) + nginx (8080) in single container
- Production data mounted read-only from `/srv/appdata/cannalchemy/`
- nginx: SPA fallback, API proxy, gzip, 1-year static asset cache

### Key Decisions

1. **Tailwind v4 (CSS-first):** No `tailwind.config.js`, uses `@theme` in CSS
2. **D3 + React integration:** D3 renders SVG inside `useEffect`, React manages state
3. **Recharts for bar charts:** Simpler than raw D3 for standard chart types
4. **Background warmup:** Entire model/graph/cache loads async — API starts instantly
5. **Production DB scale:** 67,477 strains, 6,553 ML-ready — much larger than dev fixtures

---

## File Inventory

### ML modules (`cannalchemy/models/`)
| File | Purpose | Phase |
|------|---------|-------|
| dataset.py | Feature/label matrix builder + engineered features | 2 |
| effect_predictor.py | XGBoost multi-label classifier, CV, calibration, save/load | 2 |

### API modules (`cannalchemy/api/`)
| File | Purpose | Phase |
|------|---------|-------|
| app.py | FastAPI API (predict, effects, features, health, strains, match, graph, stats) | 2 + 3 |

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
| consumer_config.py | URL builders + scrape config + Firecrawl key | 1C |
| allbud_scraper.py | AllBud HTML parser (BeautifulSoup) | 1C |
| leafly_scraper.py | Leafly markdown/JSON parser | 1C |
| consumer_mapper.py | Effect name → canonical mapping | 1C |
| consumer_import.py | Import consumer data to effect_reports | 1C |
| confidence.py | Multi-source confidence scoring | 1C |
| consumer_pipeline.py | Consumer scraping pipeline CLI | 1C |
| review_extractor.py | Regex + LLM effect extraction from review text | 1C.2 |
| review_pipeline.py | Review extraction pipeline CLI | 1C.2 |

### Frontend (`frontend/`)
| File | Purpose | Phase |
|------|---------|-------|
| src/pages/Landing.jsx | Landing page with hero radar, feature cards, stats | 3 |
| src/pages/Explorer.jsx | Effect picker, strain search, match results | 3 |
| src/pages/StrainDetail.jsx | Full strain profile with predictions/pathways | 3 |
| src/pages/Compare.jsx | Side-by-side strain comparison | 3 |
| src/pages/Graph.jsx | Interactive knowledge graph visualization | 3 |
| src/pages/Quality.jsx | Data quality dashboard with charts | 3 |
| src/charts/TerpeneRadar.jsx | SVG radar chart for terpene profiles | 3 |
| src/charts/EffectBars.jsx | Horizontal probability bar chart | 3 |
| src/charts/HeroRadar.jsx | Animated landing page radar | 3 |
| src/charts/PathwayDiagram.jsx | D3 force-directed pathway graph | 3 |
| src/components/StrainCard.jsx | Strain card with compositions/effects | 3 |
| src/components/EffectChip.jsx | Toggleable effect selection button | 3 |
| src/components/TypeBadge.jsx | Colored strain type indicator | 3 |
| src/components/Navbar.jsx | Navigation bar | 3 |
| src/lib/api.js | API client functions | 3 |
| e2e/smoke.spec.js | Landing, navigation, API integration tests | 3 |
| e2e/explorer.spec.js | Explorer, strain detail tests | 3 |

### Deploy (`deploy/`)
| File | Purpose | Phase |
|------|---------|-------|
| nginx.conf | SPA routing + API proxy + static cache | 3 |
| supervisord.conf | Process manager for uvicorn + nginx | 3 |

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
| test_consumer_config.py | 7 | 1C |
| test_allbud_scraper.py | 11 | 1C |
| test_leafly_scraper.py | 8 | 1C |
| test_consumer_mapper.py | 8 | 1C |
| test_consumer_import.py | 5 | 1C |
| test_confidence.py | 4 | 1C |
| test_consumer_pipeline.py | 2 | 1C |
| test_review_extractor.py | 14 | 1C.2 |
| test_review_pipeline.py | 8 | 1C.2 |
| test_dataset.py | 15 | 2 |
| test_effect_predictor.py | 12 | 2 |
| test_api.py | 8 | 2 |
| **Total (pytest)** | **182 (179 run + 3 network)** | |
| **E2E (Playwright)** | **24** | 3 |

### Docs
| File | Purpose |
|------|---------|
| docs/plans/2026-02-20-cannalchemy-design.md | Original system design |
| docs/plans/2026-02-20-cannalchemy-phase1-plan.md | Phase 1 implementation plan |
| docs/plans/2026-02-20-dataset-enrichment-design.md | 1A/1B/1C enrichment design (approved) |
| docs/plans/2026-02-20-phase1a-data-cleaning.md | Phase 1A implementation plan (7 tasks) |
| docs/plans/2026-02-20-phase1b-cannlytics-import.md | Phase 1B implementation plan (7 tasks) |
| docs/plans/2026-02-20-phase1c-consumer-data.md | Phase 1C implementation plan (7 tasks) |
| docs/SESSION-LOG.md | This file — cross-session tracking |
| docs/plans/2026-02-20-phase3-design.md | Phase 3 UI design — The Apothecary Lab |
| docs/plans/2026-02-20-phase3-implementation.md | Phase 3 implementation plan (14 tasks) |

---

## Dependencies

```
# pyproject.toml
networkx, rapidfuzz, httpx, pandas, sqlalchemy, huggingface_hub, openpyxl, beautifulsoup4
# ml: scikit-learn, xgboost
# api: fastapi, uvicorn
# dev: pytest

# frontend (package.json)
react 19, react-dom, react-router-dom 7, d3 7, recharts 3
# dev: vite 7, @vitejs/plugin-react, tailwindcss 4, @playwright/test
```

### Trained models (`data/models/`)
| Dir | Features | Mean AUC | Notes |
|-----|----------|----------|-------|
| v1/ | 27 (raw molecules) | 0.802 | Baseline |
| v2/ | 35 (+ engineered) | 0.811 | Production model (API default) |

## Z.AI API

- Endpoint: `https://api.z.ai/api/anthropic/v1/messages`
- Model: `glm-4.7`
- API key: stored in `~/config/n8n.env` as `ZAI_API_KEY`
- Used for: LLM effect classification (Phase 1A Task 3), strain explanations (Phase 5)

---

## Phase 5: LLM Explanations (COMPLETE)

**Branch:** `worktree-phase5-llm`
**Tests:** 222 passing (27 new: 20 unit + 7 integration)

Added pluggable LLM explanation layer that generates human-readable prose explaining why predicted effects occur at the molecular level.

### What was built:
- **`cannalchemy/explain/llm.py`** — LLMClient with Z.AI (Anthropic-compatible) primary + Ollama fallback, rate limit handling, prompt templates for full explanations and 1-line summaries
- **`cannalchemy/explain/cache.py`** — ExplanationCache backed by `strain_explanations` SQLite table, keyed by (strain_id, type, model_version)
- **`GET /strains/{name}/explain`** — Returns cached or freshly-generated explanation with provider tag
- **`POST /match` `explain` flag** — Adds 1-line AI summaries to match results
- **StrainDetail AI Analysis section** — Shows explanation with skeleton loader and provider badge, hidden if LLM unavailable
- **Explorer AI Summaries toggle** — Pill button enables/disables 1-line summaries on strain cards
- **Docker config** — `cannalchemy.env` for LLM credentials, `extra_hosts` for Ollama access, DB mount changed to read-write

### Architecture:
```
Client request → /strains/{name}/explain
  → Check SQLite cache (strain_id, "full", model_version)
  → Cache hit: return cached content
  → Cache miss: build strain_data → LLMClient._generate()
    → Try Z.AI (Anthropic API) → 429? rate-limit 60s
    → Fallback to Ollama (/api/generate)
    → Cache result → return
```

### Environment variables:
- `CANNALCHEMY_LLM_PRIMARY_URL` — Z.AI endpoint
- `CANNALCHEMY_LLM_PRIMARY_MODEL` — glm-4.7
- `CANNALCHEMY_LLM_PRIMARY_KEY` — API key
- `CANNALCHEMY_LLM_FALLBACK_URL` — Ollama (http://host.docker.internal:11434)
- `CANNALCHEMY_LLM_FALLBACK_MODEL` — llama3.2
