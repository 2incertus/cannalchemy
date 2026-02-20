# Cannalchemy Design Document

**Date:** 2026-02-20
**Status:** Approved
**Author:** Mathias + Claude

## Vision

An open-source AI system that predicts cannabis effects from terpene/cannabinoid chemistry (and vice versa), grounded in molecular pharmacology data. Differentiates from existing tools by explaining *why* at the molecular level — which receptor pathways drive which effects — with beautiful, digestible visualizations and quantified confidence.

## Primary Users

1. **Consumers** — "I want to feel X, what strain/profile achieves that?"
2. **Researchers** — "How do terpene-cannabinoid interactions produce the entourage effect?"
3. **Breeders** (future phase) — "What should I cross to produce a target chemical profile?"

## Relationship to Strain Tracker

Cannalchemy is a **separate project** from the existing Strain Tracker (port 8420). It lives in its own repository/directory with its own backend, models, and frontend. It can import data from Strain Tracker's SQLite database as one of several data sources, but has no runtime dependency on it.

## Architecture

### Data Layer: SQLite + NetworkX Hybrid

**SQLite** for persistent, queryable storage of all raw and processed data. Single-file database — portable, easy to back up, no server process needed.

**NetworkX** for in-memory graph representation of molecular interaction networks. Built from SQLite data on app startup (~1-2s). Used for relationship traversal, pathway queries, and feeding visualizations.

```
SQLite (persistent on disk)
├── molecules          (name, smiles, molecular_weight, type, pubchem_id, ...)
├── receptors          (name, uniprot_id, location, function)
├── binding_affinities (molecule_id, receptor_id, ki_value, source, ...)
├── strains            (name, type, thc/cbd ranges, description, ...)
├── strain_compositions(strain_id, molecule_id, percentage)
├── effects            (name, category, description)
├── effect_reports     (strain_id, effect_id, report_count, source)
└── lab_results        (strain_name, lab, state, test_date, molecule_id, concentration)

          ↓ on app startup (~1-2s) ↓

NetworkX Graph (in memory)
├── Nodes: molecules, receptors, effects, strains
├── Edges: binds_to (affinity weight), contains (percentage), produces (probability)
└── Queries: pathway traversal, synergy detection, visualization data
```

**Why this hybrid:**
- SQLite handles structured queries ("all strains where myrcene > 0.3% and THC > 18%")
- NetworkX handles graph traversal ("trace paths from limonene to anxiety-relief through receptor interactions")
- No external database server to install (important for open-source adoption)
- The molecular interaction graph is small (~50-100 core nodes) — fits in memory trivially

### Data Sources

| Source | Data | Quality | Availability |
|--------|------|---------|-------------|
| **Strain Tracker DB** | 25K+ strains, terpene profiles (20 terpenes), effects, user reviews | Medium (crowdsourced) | Immediate |
| **State lab databases** (CO, OR, WA) | Mandatory testing: exact terpene/cannabinoid concentrations | High (certified labs) | Requires ETL pipeline |
| **PubChem** | Molecular structures (SMILES), properties (MW, LogP, TPSA) | High (curated) | Free API |
| **ChEMBL** | Receptor binding affinities (CB1, CB2, TRPV1, serotonin, etc.) | High (peer-reviewed) | Free API |
| **Leafly / AllBud / Reddit** | User-reported effects, reviews, strain descriptions | Medium-low (subjective) | Scraping required |

**Data distribution:** Full dataset committed to the repository. Scraping tools also included so users can refresh/extend data independently.

### ETL Pipeline

A proper ETL (Extract-Transform-Load) pipeline handles data ingestion:

1. **Extract** — API clients for PubChem, ChEMBL; parsers for state lab CSVs/PDFs; scrapers for consumer platforms; importer for Strain Tracker SQLite
2. **Transform** — Strain name normalization/deduplication (fuzzy matching), unit standardization, molecular fingerprint computation (RDKit), data quality scoring
3. **Load** — Into Cannalchemy's SQLite schema, with source provenance tracking

The strain name matching problem (e.g., "Blue Dream" vs "BlueDream" vs "Blue Dream #3") is solved with fuzzy string matching (rapidfuzz) + manual alias tables for common variants.

## ML Approach

### Phased Strategy

| Phase | Approach | Where it runs | Why |
|-------|----------|---------------|-----|
| **Phase 1** | No ML | N/A | Focus on data quality and knowledge graph |
| **Phase 2** | XGBoost/sklearn ensemble | N100 (CPU) or gaming PC | Robust for tabular data, fast training, explainable feature importance |
| **Phase 3** | GNN upgrade (PyTorch Geometric) | Gaming PC (4070 Ti, 12GB VRAM) | When ChEMBL enrichment expands molecule set beyond the core 20 terpenes |

**Why start classical:** The molecular vocabulary is small (20 terpenes, ~6 cannabinoids). GNNs need diverse molecular structures to learn structure-activity relationships. With 20 repeated molecules, classical ML outperforms and doesn't overfit.

**When to upgrade:** Once ChEMBL data adds hundreds of related terpenoids, minor cannabinoids, and flavonoids, the GNN can learn from molecular graph topology — generalizing to compounds the model hasn't seen.

### Prediction Models

**Forward (chemistry → effects):**
- Input: Terpene percentages (20D) + cannabinoid concentrations (THC, CBD, CBN, CBC, CBG, THCV) + molecular descriptors from RDKit
- Output: Per-effect probabilities with calibrated confidence intervals
- Method: Ensemble of models trained on different data sources (strain-tracker reviews, Leafly data, lab-correlated effects). Each model votes; agreement/disagreement shown to user.
- Calibration: Platt scaling or isotonic regression to convert raw scores to true probabilities.

**Reverse (effects → chemistry):**
- Input: Desired effect profile (e.g., maximize relaxation + creativity, minimize anxiety)
- Output: Optimal terpene/cannabinoid ratios + closest matching known strains
- Method: Constrained optimization over the forward model's parameter space
- Phase 3+ — designed after forward model is validated

**Breeding suggestions (future):**
- Input: Target chemical profile from reverse prediction
- Output: Parent strain pairs whose genetic crossing could approximate the target
- Requires normalized lineage/genetics data (currently unstructured in strain descriptions)

### Ensemble Architecture

```
Input: Terpene/Cannabinoid Profile
         │
    ┌────┼────┬────────────┐
    ▼    ▼    ▼            ▼
  Model  Model  Model    Model
  (your  (Leafly (Lab    (Reddit
   DB)    data)  data)    data)
    │    │    │            │
    ▼    ▼    ▼            ▼
  P(effect) per model (calibrated)
         │
    ┌────┴────┐
    ▼         ▼
  Aggregated    Source
  Prediction    Agreement
  ± Confidence  Map
```

## LLM Explanation Layer

**Pluggable** — any OpenAI-compatible API endpoint. No hard dependency on any provider.

Configuration:
```
CANNALCHEMY_LLM_BASE_URL=https://api.z.ai/api/anthropic/v1/messages
CANNALCHEMY_LLM_MODEL=glm-4.7
CANNALCHEMY_LLM_API_KEY=<key>
```

The LLM receives structured model output (predicted effects, confidence, key chemical factors, receptor pathway data) and generates a human-readable explanation. Example:

> "Blue Dream's terpene profile is dominated by myrcene (0.35%) and limonene (0.28%), with moderate caryophyllene (0.15%). Myrcene's strong CB1 receptor affinity (Ki=0.45uM) drives the relaxation effect (predicted 83% +/- 7%), while limonene's interaction with serotonin receptors contributes to the mood-elevating creativity (45% +/- 12%). The low caryophyllene level limits CB2 anti-inflammatory activation, which is why pain relief scores lower (28% +/- 15%)."

The ML models make the predictions. The LLM just translates them into prose.

## Frontend

### Stack
- **React** (consistent with existing Strain Tracker knowledge)
- **D3.js** for custom molecular/receptor pathway visualizations
- **Recharts** for standard charts (bar, line, radar)
- **Tailwind CSS** for styling

### Key Visualizations

1. **Terpene Radar Charts** — Spider/radar chart showing the terpene "fingerprint" of a strain. Instantly communicates the chemical shape. Supports overlaying multiple strains for comparison.

2. **Receptor Pathway Diagrams** — Interactive flowchart: Molecule -> binds Receptor (with affinity weight) -> modulates Neurotransmitter -> produces Effect. This is the unique differentiator — no existing tool visualizes molecular mechanisms of cannabis effects.

3. **Effect Probability Bars** — Horizontal bars ranked by predicted probability, with confidence intervals displayed. Clear, actionable output: "Relaxation: 83% +/- 7%".

4. **Strain Comparison View** — Side-by-side overlay of 2-3 strains showing terpene profiles, predicted effects, and chemical differences. Highlights where profiles diverge.

### Pages

- **Explorer** — Query interface: "I want to feel..." -> predicted profiles + matching strains
- **Strain Analysis** — Deep dive into a single strain: chemistry, predicted effects, receptor pathways, LLM explanation
- **Compare** — Side-by-side strain comparison with all visualizations
- **Knowledge Graph** — Interactive exploration of the molecular interaction network
- **Data Quality** — Dashboard showing data coverage, source breakdown, confidence in different data regions

## Deployment

| Component | Where | Notes |
|-----------|-------|-------|
| Web app + API (inference) | N100 mini-PC (Docker) | Lightweight — model artifacts loaded at startup, inference is CPU-friendly for classical ML |
| Model training (XGBoost) | N100 or gaming PC | XGBoost trains in seconds on this data volume |
| Model training (GNN, Phase 3) | Gaming PC (4070 Ti, 32GB RAM) | GPU required for PyTorch Geometric |
| Data pipeline / scraping | N100 | Runs as batch jobs, not latency-sensitive |

Trained model artifacts (ONNX or joblib format, ~1-50MB) exported from gaming PC, deployed to N100's data volume.

## Project Structure

```
cannalchemy/
├── pyproject.toml              # Package metadata, dependencies
├── README.md                   # Project overview, setup instructions
├── LICENSE                     # MIT
├── cannalchemy/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── pubchem.py          # PubChem API client (molecular structures)
│   │   ├── chembl.py           # ChEMBL API client (binding affinities)
│   │   ├── state_labs.py       # State lab data parsers (CO, OR, WA)
│   │   ├── strain_import.py    # Import from Strain Tracker SQLite
│   │   ├── scrapers.py         # Leafly, AllBud, Reddit scrapers
│   │   ├── normalize.py        # Strain name matching/deduplication
│   │   ├── schema.py           # SQLAlchemy or raw SQL schema definitions
│   │   └── graph.py            # NetworkX graph builder from SQLite data
│   ├── molecules/
│   │   ├── __init__.py
│   │   ├── fingerprints.py     # RDKit Morgan/MACCS fingerprints
│   │   ├── descriptors.py      # Molecular properties (MW, LogP, TPSA)
│   │   └── similarity.py       # Tanimoto similarity, molecular distance
│   ├── models/
│   │   ├── __init__.py
│   │   ├── effect_predictor.py # Forward model: chemistry -> effects
│   │   ├── profile_optimizer.py# Reverse model: desired effects -> chemistry
│   │   ├── breeding.py         # Parent strain selection (future)
│   │   ├── ensemble.py         # Multi-source ensemble aggregation
│   │   └── evaluation.py       # Metrics, cross-validation, calibration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI application
│   │   └── routes.py           # Prediction + data endpoints
│   └── explain/
│       ├── __init__.py
│       └── llm.py              # Pluggable LLM explanation generation
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/              # Explorer, Analysis, Compare, Graph, DataQuality
│   │   └── components/         # TerpeneRadar, PathwayDiagram, EffectBars, etc.
│   ├── package.json
│   └── vite.config.js
├── notebooks/
│   ├── 01-data-exploration.ipynb
│   ├── 02-molecular-features.ipynb
│   └── 03-model-training.ipynb
├── data/
│   ├── raw/                    # Downloaded/scraped datasets
│   ├── processed/              # Cleaned, featurized
│   └── models/                 # Trained model artifacts (ONNX/joblib)
├── tests/
│   ├── test_data.py
│   ├── test_molecules.py
│   └── test_models.py
├── Dockerfile
└── docker-compose.yml
```

## Implementation Phases

### Phase 1: Data Foundation (Current Priority)
- Set up project structure, pyproject.toml, dev environment
- Build ETL pipeline: Strain Tracker import, PubChem client, ChEMBL client
- Build state lab data parsers (CO, OR, WA)
- Build consumer platform scrapers (Leafly, AllBud, Reddit)
- Implement strain name normalization/deduplication
- Design and populate SQLite schema
- Build NetworkX graph from SQLite data
- Create exploratory Jupyter notebooks showing terpene-effect correlations
- Compute RDKit molecular fingerprints and descriptors for all molecules

### Phase 2: Effect Prediction
- Train forward model (chemistry -> effects) with XGBoost
- Implement ensemble architecture (per-source models)
- Calibrate probabilities (Platt scaling / isotonic regression)
- Build FastAPI endpoints for predictions
- Cross-validation and evaluation metrics

### Phase 3: Visualization + UI
- React frontend scaffolding
- Terpene radar charts (D3.js)
- Receptor pathway diagrams (D3.js force-directed graph)
- Effect probability bars with confidence intervals (Recharts)
- Strain comparison views
- Knowledge graph explorer

### Phase 4: Reverse Prediction
- Constrained optimization: desired effects -> ideal chemistry
- Closest existing strain matching
- Gap analysis (how each match differs from ideal)

### Phase 5: LLM Explanations
- Pluggable LLM client (OpenAI-compatible)
- Prompt engineering for scientific explanations
- Integration with prediction API responses

### Phase 6: GNN Upgrade
- Expand molecule set via ChEMBL (terpenoids, minor cannabinoids, flavonoids)
- PyTorch Geometric model architecture
- Train on gaming PC (4070 Ti)
- Evaluate vs. XGBoost baseline — only deploy if it outperforms

### Phase 7: Breeding Optimization (Future)
- Normalize genetic lineage data from strain descriptions
- Parent strain selection algorithm
- Target chemical profile approximation

## Key Dependencies

### Python
- `rdkit` — Molecular fingerprinting, SMILES parsing, chemical informatics
- `scikit-learn` — Classical ML models, evaluation
- `xgboost` — Gradient boosted trees (primary model)
- `networkx` — In-memory knowledge graph
- `fastapi` + `uvicorn` — API server
- `httpx` — Async HTTP client (PubChem, ChEMBL, LLM APIs)
- `rapidfuzz` — Fuzzy string matching for strain name normalization
- `pandas` — Data manipulation
- `jupyter` — Notebooks for exploration

### Frontend
- `react` — UI framework
- `d3` — Custom visualizations (pathway diagrams, terpene wheels)
- `recharts` — Standard charts
- `tailwindcss` — Styling

### Future (Phase 6+)
- `torch` + `torch_geometric` — Graph neural networks
- `plotly` — Additional interactive visualizations

## Open Questions (To Resolve During Implementation)

1. **Reverse prediction constraints** — Skipped during design; revisit when forward model is working
2. **Lab data format specifics** — Need to research exact formats from CO/OR/WA state databases
3. **Reddit scraping approach** — API (Pushshift/official) vs. web scraping vs. existing datasets
4. **Model versioning** — How to track and deploy model iterations (MLflow? Simple file versioning?)
5. **Strain lineage normalization** — How to extract parent strain relationships from unstructured descriptions
