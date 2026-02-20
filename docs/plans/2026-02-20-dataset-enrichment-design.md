# Cannalchemy Dataset Enrichment — Design Document

**Date:** 2026-02-20
**Status:** Approved
**Prerequisite:** Phase 1 Data Foundation (complete)
**Goal:** Clean, expand, and enrich the dataset to ML-readiness before Phase 2 training.

---

## Problem Statement

Phase 1 imported 24,853 strains from Strain Tracker, but the dataset has critical quality issues that would undermine ML training:

1. **Effects taxonomy is garbage** — 2,171 "effects" where ~95% are scraped sentence fragments, not real effects. Only 6 medical effects and 2 negative effects.
2. **Null pollution** — 8,434 effect reports with "null" as the effect (25.5% of all reports).
3. **Thin terpene profiles** — 13,598 strains have only 3 terpenes; only 2,398 have full 8-terpene panels.
4. **Missing cannabinoids** — Only THC and CBD in the DB; CBN, CBG, CBC, THCV missing (despite having SMILES data).
5. **No lab-tested data** — All 78K compositions are self-reported; the `lab_results` table is empty.
6. **Only 6,211 ML-ready strains** (25%) have both terpene AND effect data.
7. **Effect duplicates** — "relaxed" and "relaxing" are separate effects; no normalization.

## Architecture

Three sequential sub-phases, each independently improving ML readiness:

```
Phase 1A: Data Cleaning          Phase 1B: Lab Data              Phase 1C: Consumer Data
┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ Canonical taxonomy   │    │ Cannlytics 1.2M recs │    │ Leafly strain pages  │
│ LLM effect mapping   │───▶│ Per-state CSV import │───▶│ AllBud strain pages  │
│ Strain dedup         │    │ Strain cross-ref     │    │ Multi-source merge   │
│ Expand molecules     │    │ Lab-grade enrichment │    │ Confidence scoring   │
│ Confidence scores    │    │ Provenance tracking  │    │                      │
└──────────────────────┘    └──────────────────────┘    └──────────────────────┘
         │                           │                           │
    Unblocks ML on             Deepens terpene           Expands effect
    existing 6.2K strains      profiles to 10-20+        reports to 100K+
```

## ML-Readiness Targets

| Metric | Current | Target |
|--------|---------|--------|
| ML-ready strains (terpene + effect) | 6,211 (25%) | 15,000+ (60%+) |
| Canonical effects | 2,171 (messy) | ~60-80 (clean, pharmacology-grounded) |
| Effect reports | 33K (8.4K null) | 100K+ (multi-source, weighted) |
| Terpenes per strain (median) | 3 | 8-12 (lab-enriched) |
| Cannabinoid types tracked | 2 | 6 (+ CBN, CBG, CBC, THCV) |
| Lab-tested compositions | 0 | 200K+ |
| Binding affinities seeded | 14/19 | 19/19 |
| Effect confidence scoring | No | Yes (multi-source weighted) |

---

## Sub-phase 1A: Data Cleaning

**Goal:** Fix existing data to be ML-ready. Unblocks training on current 6.2K strains.

### Task 1A.1: Canonical Effects Taxonomy

Build a pharmacology-grounded effects taxonomy with consumer-friendly labels:

**Positive (~25):** relaxed, euphoric, happy, creative, energetic, focused, uplifted, giggly, talkative, tingly, aroused, hungry, sleepy, calm, social, motivated, inspired, meditative, body-high, head-high, etc.

**Negative (~15):** dry-mouth, dry-eyes, dizzy, paranoid, anxious, headache, nausea, rapid-heartbeat, couch-lock, disoriented, fatigue, irritable, etc.

**Medical (~20):** pain, stress, anxiety, depression, insomnia, nausea, appetite-loss, inflammation, muscle-spasms, seizures, ptsd, migraines, fatigue, cramps, eye-pressure, arthritis, fibromyalgia, adhd, bipolar, etc.

Store in a new `canonical_effects` table with:
- `id`, `name`, `category` (positive/negative/medical)
- `description` (pharmacology grounding — which receptors/pathways relate)
- `synonyms` (JSON array of known alternate names)

### Task 1A.2: LLM Effect Mapping

Send the 2,171 existing effects to GLM-4.7 in batches of ~50:
- Input: effect name string
- Output: canonical effect name, or "JUNK" if unmappable
- Store mappings in an `effect_mappings` table: `(raw_name, canonical_id, confidence, method)`
- Method: "llm_classification" with model name for provenance

### Task 1A.3: Rebuild Effect Reports

- Re-link all effect_reports through the canonical mapping
- Drop reports where raw effect maps to "JUNK" or "null"
- Merge duplicate reports (e.g., "relaxed" + "relaxing" → same canonical)
- Add `confidence` column to effect_reports (default 1.0 for single-source)

### Task 1A.4: Strain Name Deduplication

- Run fuzzy matching across all 24,853 normalized strain names
- Identify clusters of near-duplicates (≥95% match)
- Merge duplicates: keep the strain with the most data, link others as aliases
- Store in `strain_aliases` table: `(alias_strain_id, canonical_strain_id)`

### Task 1A.5: Expand Molecules

- Add CBN, CBG, CBC, THCV to molecules table from KNOWN_COMPOUNDS cache
- Seed the 5 missing binding affinities (CBN→CB1, CBN→CB2, CBG→CB1, CBG→CB2, CBG→5-HT1A)
- Run PubChem enrichment for LogP and TPSA on all 27 molecules

### Task 1A.6: Effect Confidence Scoring

- Add `confidence` field to effect_reports (0.0 to 1.0)
- Score based on: number of sources reporting, vote counts (if available), consistency with molecular pathways
- Initial scoring: 1.0 for single-source, boosted in 1C when multi-source data arrives

---

## Sub-phase 1B: Cannlytics Lab Data

**Goal:** Import 1.2M lab test records with lab-grade terpene/cannabinoid concentrations.

### Data Source

- **Dataset:** `cannlytics/cannabis_results` on HuggingFace
- **License:** CC BY 4.0
- **Size:** ~1.2M records across 14 US states, 6.28 GB total
- **Download:** Per-state CSVs via `huggingface_hub`
- **Reference:** `cannlytics/cannabis_analytes` (16 cannabinoids + 21 terpenes with chemical properties)

### Known Data Quality Issues

- All values stored as strings (except Alaska THC/CBD)
- Sentinel values: `0.000000001` = Not Detected, `0.0000001` = Below LOQ
- Schema varies wildly per state (Michigan: 8 fields, Connecticut: 200+)
- Strain names are free-text, no standardization
- Non-random sampling (overrepresents some labs/producers)

### Task 1B.1: Download Pipeline

- Install `huggingface_hub` dependency
- Download per-state CSVs, starting with richest: WA (203K), OR (197K), NV (153K), MD (105K), MI (90K), MA (75K), CA (72K)
- Skip thin states initially: NY (330), UT (1.2K)
- Store raw CSVs in `data/raw/cannlytics/{state}/`

### Task 1B.2: Schema Discovery & Column Mapping

Build a mapper for each state that:
- Identifies which cannabinoid columns exist (e.g., `delta_9_thc` → `thc`, `cbga` → `cbg`)
- Identifies which terpene columns exist (e.g., `alpha_pinene` → `pinene`, `beta_myrcene` → `myrcene`, `d_limonene` → `limonene`, `beta_caryophyllene` → `caryophyllene`)
- Maps to our molecule names
- Reports which molecules are available per state

### Task 1B.3: Value Cleaning

- Convert string concentrations to floats
- Handle sentinel values: ND (`0.000000001`) → NULL, LOQ (`0.0000001`) → NULL
- Drop rows with no usable analyte data
- Validate ranges (reject concentrations > 100% or < 0)
- Store cleaned data in `lab_results` table

### Task 1B.4: Strain Cross-Reference

- Normalize Cannlytics strain names using our `normalize_strain_name()`
- Fuzzy-match against existing strains at ≥90% confidence
- Create new strain entries for unmatched names (source="cannlytics")
- Update `strain_compositions` with lab-tested data: `measurement_type='lab_tested'`
- When both lab-tested and reported data exist, keep both (ML can weight them)

### Task 1B.5: Provenance Tracking

- Record each state import in `data_sources` table
- Tag all lab compositions with source state and lab name
- Track import timestamps for incremental updates

---

## Sub-phase 1C: Consumer Data

**Goal:** Expand effect reports with structured consumer platform data.

### Task 1C.1: Leafly Strain Scraping

- Scrape Leafly strain pages for our existing strains
- URL pattern: `leafly.com/strains/{normalized-strain-name}`
- Extract: effects (with vote counts), flavors, medical uses, negatives, THC/CBD ranges, ratings, review count
- Use Firecrawl MCP or httpx with respectful rate limiting (1 req/sec)
- Store raw responses for reproducibility

### Task 1C.2: AllBud Strain Scraping

- Scrape AllBud strain pages as secondary source
- Extract: effects, medical uses, negatives, flavors, ratings
- Cross-validate against Leafly data

### Task 1C.3: Consumer Data Integration

- Map Leafly/AllBud effects to canonical taxonomy (from 1A)
- Import effect reports with vote counts where available
- Update confidence scores: strains with 2+ sources get higher confidence
- Add `source` tracking to all new effect reports

---

## Schema Changes

New tables needed:

```sql
-- Canonical effects (clean taxonomy)
CREATE TABLE IF NOT EXISTS canonical_effects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT CHECK(category IN ('positive', 'negative', 'medical')) NOT NULL,
    description TEXT DEFAULT '',
    synonyms TEXT DEFAULT '[]',  -- JSON array
    receptor_pathway TEXT DEFAULT ''  -- e.g., "CB1 activation"
);

-- Effect name mappings (raw -> canonical)
CREATE TABLE IF NOT EXISTS effect_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL,
    canonical_id INTEGER REFERENCES canonical_effects(id),
    confidence REAL DEFAULT 1.0,
    method TEXT DEFAULT '',  -- "llm_classification", "manual", "fuzzy_match"
    UNIQUE(raw_name)
);

-- Strain aliases (deduplication)
CREATE TABLE IF NOT EXISTS strain_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_strain_id INTEGER NOT NULL REFERENCES strains(id),
    canonical_strain_id INTEGER NOT NULL REFERENCES strains(id),
    match_score REAL DEFAULT 0.0,
    UNIQUE(alias_strain_id)
);
```

Modified tables:
- `effect_reports`: add `confidence REAL DEFAULT 1.0` column
- `strain_compositions`: no schema change, but `measurement_type='lab_tested'` distinguishes lab data

---

## Dependencies

### New Python packages
- `huggingface_hub` — Download Cannlytics dataset
- No new packages for 1A (uses existing httpx for LLM API)

### External APIs
- GLM-4.7 via z.ai API (for LLM effect classification in 1A)
- Leafly.com / AllBud.com (web scraping in 1C)

### Existing infrastructure
- Strain Tracker DB at `/srv/appdata/strain-tracker/strain-tracker.db` (read-only)
- PubChem API (for molecule enrichment)

---

## Success Criteria

Phase is complete when:
1. All 24 existing tests still pass
2. Canonical effects taxonomy has 60-80 entries across 3 categories
3. Effect reports are cleaned (no nulls, no junk, all mapped to canonical)
4. All 6 cannabinoids in DB with 19/19 binding affinities
5. Cannlytics lab data imported for ≥5 states
6. ML-ready strains ≥15,000 (terpene + effect data)
7. Lab-tested compositions ≥200,000
8. Leafly + AllBud effect data imported for ≥5,000 strains
9. Effect confidence scores populated for all reports
