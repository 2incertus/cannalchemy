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

## Quick Start

```bash
# Clone and install
git clone https://github.com/yourusername/cannalchemy.git
cd cannalchemy
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"

# Run the data pipeline
cannalchemy --db-path data/processed/cannalchemy.db
```

## Status

**Phase 1: Data Foundation** (in progress)
- [ ] SQLite schema and data models
- [ ] Strain Tracker import (25K+ strains)
- [ ] PubChem molecular data enrichment
- [ ] ChEMBL receptor binding data
- [ ] NetworkX knowledge graph
- [ ] Exploratory analysis notebooks

**Future Phases:**
- Phase 2: Effect prediction (XGBoost ensemble)
- Phase 3: Visualization + React UI
- Phase 4: Reverse prediction (effects → chemistry)
- Phase 5: LLM explanations
- Phase 6: GNN upgrade
- Phase 7: Breeding optimization

## License

MIT
