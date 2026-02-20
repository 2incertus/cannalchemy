# Cannalchemy

AI-powered cannabis effect prediction grounded in molecular pharmacology.

Predicts effects from terpene/cannabinoid chemistry (and vice versa) using
ensemble ML models, molecular fingerprints, and receptor binding data.

## What Makes This Different

Most strain recommendation tools rely on crowdsourced labels ("relaxing", "energetic"). Cannalchemy goes deeper:

- **Molecular grounding** — Uses actual SMILES structures, RDKit fingerprints, and PubChem data
- **Receptor pathway modeling** — Maps how terpenes and cannabinoids interact with CB1, CB2, TRPV1, serotonin receptors
- **Quantified confidence** — Ensemble models with calibrated probabilities, not just ranked guesses
- **Explains WHY** — Traces the molecular pathway from chemistry to effect, not just correlation

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Data Sources   │────▶│  SQLite + Graph   │────▶│   ML Ensemble   │
│                 │     │                  │     │                 │
│ Strain Tracker  │     │ SQLite (storage) │     │ XGBoost models  │
│ PubChem         │     │ NetworkX (graph) │     │ Per-source      │
│ ChEMBL          │     │                  │     │ Calibrated      │
│ State lab data  │     │ Molecules        │     │                 │
│ Leafly/AllBud   │     │ Receptors        │     └────────┬────────┘
└─────────────────┘     │ Bindings         │              │
                        │ Strains          │     ┌────────▼────────┐
                        │ Effects          │     │  LLM Explainer  │
                        └──────────────────┘     │ (pluggable API) │
                                                 └────────┬────────┘
                                                          │
                                                 ┌────────▼────────┐
                                                 │    React + D3   │
                                                 │                 │
                                                 │ Terpene wheels  │
                                                 │ Pathway diagrams│
                                                 │ Effect bars     │
                                                 │ Strain compare  │
                                                 └─────────────────┘
```

## Data Foundation (Phase 1)

| Component | Count |
|-----------|-------|
| Strains | 24,853 (from Strain Tracker) |
| Molecules | 23 (21 terpenes + 2 cannabinoids) |
| SMILES structures | 28 (21 terpenes + 6 cannabinoids + 1 variant) |
| Receptors | 6 (CB1, CB2, TRPV1, 5-HT1A, PPARgamma, GPR55) |
| Binding affinities | 19 (literature-sourced Ki values) |
| Strain compositions | 78,985 (terpene/cannabinoid percentages) |
| Effects taxonomy | 2,179 (positive, negative, medical) |
| Effect reports | 40,841 (strain-effect links) |
| Knowledge graph | 19,260 nodes, 99,579 edges |

## Quick Start

```bash
# Clone and install
git clone https://github.com/2incertus/cannalchemy.git
cd cannalchemy
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the data pipeline (requires Strain Tracker DB)
cannalchemy --db-path data/processed/cannalchemy.db --skip-pubchem

# Run tests
pytest tests/ -v -k "not network"
```

## Status

**Phase 1: Data Foundation** (complete)
- [x] SQLite schema (9 tables, indexed)
- [x] Strain Tracker import (24,853 strains)
- [x] PubChem molecular data (28 SMILES cached, API fallback)
- [x] ChEMBL receptor binding data (6 receptors, 19 affinities)
- [x] NetworkX knowledge graph with pathway traversal
- [x] Strain name normalization with fuzzy matching
- [x] Data pipeline CLI
- [x] Exploratory analysis notebook
- [x] 24 tests passing

**Future Phases:**
- Phase 2: Effect prediction (XGBoost ensemble)
- Phase 3: Visualization + React UI
- Phase 4: Reverse prediction (effects → chemistry)
- Phase 5: LLM explanations
- Phase 6: GNN upgrade
- Phase 7: Breeding optimization

## License

MIT
