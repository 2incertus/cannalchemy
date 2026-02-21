# CLAUDE.md — Cannalchemy

AI-powered cannabis effect prediction from terpene/cannabinoid chemistry, grounded in molecular pharmacology.

## Project Structure

```
cannalchemy/
├── cannalchemy/          # Python package
│   ├── data/             # ETL modules (schema, importers, scrapers, graph, taxonomy)
│   ├── models/           # ML models (XGBoost effect predictor, dataset builder)
│   ├── explain/          # LLM explanation layer (client, cache, prompts)
│   └── api/              # FastAPI app (predict, strains, match, graph, stats, explain)
├── frontend/             # React 19 + Vite 7 + Tailwind v4 + D3 + Recharts
│   ├── src/pages/        # Landing, Explorer, StrainDetail, Compare, Graph, Quality
│   ├── src/charts/       # TerpeneRadar, EffectBars, HeroRadar, PathwayDiagram
│   ├── src/components/   # StrainCard, EffectChip, TypeBadge, Nav
│   └── e2e/              # Playwright E2E tests
├── deploy/               # nginx.conf, supervisord.conf
├── tests/                # pytest (222 tests)
├── data/                 # Local data (not in git): processed/, models/, raw/
├── docs/                 # Plans, session log, design docs
├── Dockerfile            # Multi-stage: Node.js build → Python + nginx
└── docker-compose.yml    # Port 8422, volumes from /srv/appdata/cannalchemy/
```

## Commands

```bash
# Run API (dev)
.venv/bin/uvicorn cannalchemy.api.app:app --host 0.0.0.0 --port 8421

# Run frontend (dev)
cd frontend && npm run dev

# Run tests
.venv/bin/pytest tests/ -v
cd frontend && npx playwright test

# Docker build + deploy
docker compose build && docker compose up -d

# Check container health
curl http://localhost:8422/api/health
curl http://localhost:8422/api/stats
```

## Key Architecture Decisions

- **SQLite + NetworkX hybrid**: SQLite for queries, NetworkX for graph traversal (built at startup)
- **XGBoost multi-label**: 51 independent binary classifiers, one per effect. Mean AUC 0.811
- **Prediction cache**: Background thread pre-computes all 6,553 ML predictions at startup (~90s on N100). Match endpoint serves from memory (<50ms)
- **threading.Event**: Prevents double cache building; match endpoint waits for background thread or falls back to synchronous build
- **Single-container Docker**: supervisord runs uvicorn (8421) + nginx (8080) together
- **Tailwind v4 CSS-first**: No tailwind.config.js — uses `@theme` blocks in CSS
- **LLM Explanations**: Z.AI (glm-4.7) primary, Ollama (llama3.2) fallback, SQLite cache

## Data

- **Production DB**: `/srv/appdata/cannalchemy/cannalchemy.db` (519MB, mounted read-write in Docker for explanation cache)
- **Models**: `/srv/appdata/cannalchemy/models.pkl` (108MB) + `metadata.json` (13KB)
- **67,477 strains**, 6,553 ML-ready (3+ molecules + effect reports)
- **Sources**: Strain Tracker (24K), Cannlytics labs (42K), AllBud, Leafly reviews

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/predict` | POST | Predict effects from chemical profile |
| `/effects` | GET | List 51 predictable effects with AUC |
| `/features` | GET | List 35 input features |
| `/health` | GET | Health check |
| `/strains` | GET | Search/list strains with compositions |
| `/strains/{name}` | GET | Full strain profile + predictions + pathways |
| `/strains/{name}/explain` | GET | LLM explanation for strain (cached) |
| `/match` | POST | Find strains matching desired effects (optional `explain` flag) |
| `/graph` | GET | Knowledge graph nodes and edges |
| `/graph/{node_id}` | GET | Subgraph centered on a node |
| `/stats` | GET | Data quality statistics |

## Code Style

- **Python**: PEP 8, type hints, try/catch around external calls
- **Frontend**: JSX functional components, hooks for state, D3 in useEffect
- **Tests**: pytest fixtures with tmp_path DBs, Playwright for E2E
- **API patterns**: `_get_predictor()` / `_get_db()` / `_get_graph()` lazy singletons

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| 1: Data Foundation | COMPLETE | 67K strains, 27 molecules, knowledge graph |
| 1A: Data Cleaning | COMPLETE | 51 canonical effects, LLM classification |
| 1B: Cannlytics Labs | COMPLETE | 1.39M lab results, 285K compositions |
| 1C: Consumer Data | COMPLETE | AllBud + Leafly + review extraction |
| 2: Effect Prediction | COMPLETE | XGBoost, AUC 0.811, FastAPI |
| 3: Visualization + UI | COMPLETE | 6 pages, Docker deployment |
| 4: Reverse Prediction | NOT STARTED | Effects → optimal chemistry |
| 5: LLM Explanations | COMPLETE | Z.AI + Ollama fallback, SQLite cache, Explorer summaries |
| 6: GNN Upgrade | NOT STARTED | PyTorch Geometric (needs GPU) |
| 7: Breeding | NOT STARTED | Parent strain selection (future) |

## Git

- Do NOT add `Co-Authored-By` trailers to commit messages
- Use worktrees for feature work: `git worktree add .claude/worktrees/<name>`
- Commit style: `feat(scope):`, `fix:`, `docs:`, `test:`
