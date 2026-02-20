# Phase 3: Visualization + UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone React frontend ("The Apothecary Lab") with 6 pages: Landing, Explorer, Strain Detail, Compare, Knowledge Graph, and Data Quality — served via Docker alongside the existing FastAPI backend.

**Architecture:** React 19 + Vite + Tailwind CSS v4 + D3.js + Recharts frontend communicating with an extended FastAPI backend via `/api` proxy. Both services run in a single `docker-compose.yml`. The backend reads from the existing SQLite DB and trained XGBoost model.

**Tech Stack:** React 19, Vite 7, Tailwind CSS 4, D3.js 7, Recharts 3, react-router-dom 7, lucide-react, FastAPI (existing), SQLite (existing), nginx

**Design Doc:** `docs/plans/2026-02-20-phase3-ui-design.md`

---

## Task 1: Extend Backend API

Add 6 new endpoints to the existing FastAPI app. These serve all data the frontend needs.

**Files:**
- Modify: `cannalchemy/api/app.py`
- Create: `tests/test_api_strains.py`

**Step 1: Write failing tests for new endpoints**

Create `tests/test_api_strains.py`:

```python
"""Tests for strain-related API endpoints."""
import sqlite3
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import CANONICAL_EFFECTS
from cannalchemy.models.effect_predictor import EffectPredictor


@pytest.fixture
def populated_db(tmp_path):
    """Create a test DB with strains, compositions, effects, and graph data."""
    db_path = str(tmp_path / "test.db")
    conn = init_db(db_path)

    # Seed molecules
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('limonene', 'terpene')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('thc', 'cannabinoid')")

    # Seed receptors
    conn.execute("INSERT INTO receptors (name, gene_name, function) VALUES ('CB1', 'CNR1', 'pain modulation')")

    # Seed binding affinities
    conn.execute(
        "INSERT INTO binding_affinities (molecule_id, receptor_id, ki_nm, action_type, source) "
        "VALUES (1, 1, 50.0, 'agonist', 'test')"
    )

    # Seed effects
    for ce in CANONICAL_EFFECTS:
        conn.execute(
            "INSERT OR IGNORE INTO effects (name, category) VALUES (?, ?)",
            (ce["name"], ce["category"]),
        )

    # Seed strains with compositions
    for i, (name, stype) in enumerate([
        ("Blue Dream", "hybrid"), ("OG Kush", "indica"), ("Sour Diesel", "sativa"),
    ], 1):
        conn.execute(
            "INSERT INTO strains (name, normalized_name, strain_type, source) VALUES (?, ?, ?, 'test')",
            (name, name.lower().replace(" ", ""), stype),
        )
        conn.execute(
            "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (?, 1, ?, 'test')",
            (i, 0.3 + i * 0.1),
        )
        conn.execute(
            "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (?, 2, ?, 'test')",
            (i, 0.2 + i * 0.05),
        )
        conn.execute(
            "INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (?, 3, ?, 'test')",
            (i, 15.0 + i * 2),
        )
        # Seed effect reports
        conn.execute(
            "INSERT INTO effect_reports (strain_id, effect_id, report_count, source) VALUES (?, 1, ?, 'test')",
            (i, 10 + i * 5),
        )

    conn.commit()
    return db_path


@pytest.fixture
def trained_predictor(tmp_path):
    """Create a minimal trained predictor."""
    rng = np.random.RandomState(42)
    n = 50
    X = pd.DataFrame({
        "myrcene": rng.uniform(0, 1, n),
        "limonene": rng.uniform(0, 1, n),
        "thc": rng.uniform(10, 30, n),
    }, index=range(1, n + 1))
    X.index.name = "strain_id"
    y = pd.DataFrame(index=X.index)
    y.index.name = "strain_id"
    y["relaxed"] = (X["myrcene"] > 0.5).astype(int)
    y["energetic"] = (X["limonene"] > 0.5).astype(int)
    predictor = EffectPredictor(calibrate=False)
    predictor.train(X, y, n_folds=3)
    save_path = str(tmp_path / "model")
    predictor.save(save_path)
    return save_path


@pytest.fixture
def client(populated_db, trained_predictor, monkeypatch):
    """Create test client with populated DB and model."""
    import cannalchemy.api.app as api_module
    monkeypatch.setattr(api_module, "DEFAULT_MODEL_DIR", trained_predictor)
    monkeypatch.setattr(api_module, "FALLBACK_MODEL_DIR", trained_predictor)
    monkeypatch.setattr(api_module, "_predictor", None)
    monkeypatch.setattr(api_module, "DB_PATH", populated_db)
    monkeypatch.setattr(api_module, "_db_conn", None)
    return TestClient(api_module.app)


class TestStrainsEndpoint:
    def test_list_strains(self, client):
        resp = client.get("/strains")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["strains"]) == 3

    def test_search_strains(self, client):
        resp = client.get("/strains?q=blue")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["strains"]) == 1
        assert data["strains"][0]["name"] == "Blue Dream"

    def test_filter_by_type(self, client):
        resp = client.get("/strains?type=indica")
        data = resp.json()
        assert all(s["strain_type"] == "indica" for s in data["strains"])

    def test_strain_has_compositions(self, client):
        resp = client.get("/strains")
        strain = resp.json()["strains"][0]
        assert "compositions" in strain
        assert len(strain["compositions"]) > 0


class TestStrainDetailEndpoint:
    def test_get_strain(self, client):
        resp = client.get("/strains/Blue Dream")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Blue Dream"
        assert "compositions" in data
        assert "predicted_effects" in data
        assert "pathways" in data

    def test_strain_not_found(self, client):
        resp = client.get("/strains/Nonexistent")
        assert resp.status_code == 404


class TestMatchEndpoint:
    def test_match_effects(self, client):
        resp = client.post("/match", json={"effects": ["relaxed"]})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["strains"]) > 0
        assert "score" in data["strains"][0]

    def test_match_with_type_filter(self, client):
        resp = client.post("/match", json={"effects": ["relaxed"], "type": "indica"})
        data = resp.json()
        assert all(s["strain_type"] == "indica" for s in data["strains"])


class TestGraphEndpoint:
    def test_get_graph(self, client):
        resp = client.get("/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0

    def test_graph_node_detail(self, client):
        resp = client.get("/graph/molecule:myrcene")
        assert resp.status_code == 200
        data = resp.json()
        assert data["node"]["name"] == "myrcene"
        assert "connected" in data


class TestStatsEndpoint:
    def test_get_stats(self, client):
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_strains" in data
        assert "ml_ready_strains" in data
        assert "molecules" in data
        assert "effects" in data
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/cannalchemy && python -m pytest tests/test_api_strains.py -v`
Expected: FAIL — endpoints don't exist yet

**Step 3: Implement new endpoints in app.py**

Add to `cannalchemy/api/app.py`:
- `DB_PATH` config (default `data/processed/cannalchemy.db`)
- `_get_db()` lazy DB connection
- `GET /strains` — query strains table with optional `q`, `type`, `limit` params; join compositions
- `GET /strains/{name}` — use `get_strain_profile()` from graph.py + predict effects
- `POST /match` — for each ML-ready strain, predict effects, compute match score (avg probability of requested effects), return sorted
- `GET /graph` — build knowledge graph, serialize nodes/edges to JSON (exclude strain nodes for performance — too many)
- `GET /graph/{node_id}` — return node + all connected nodes/edges
- `GET /stats` — aggregate counts from DB tables
- Add CORS middleware (`allow_origins=["*"]`) for dev, restrict in production

Key implementation notes:
- Import `build_knowledge_graph`, `get_strain_profile`, `get_molecule_pathways` from `cannalchemy.data.graph`
- `_get_db()` opens SQLite with `check_same_thread=False` for FastAPI
- `/match` uses the existing `predict_effects` logic but loops over strains server-side
- `/graph` caches the graph in a global (expensive to build, ~2s) — rebuild on startup only
- `/strains` returns compositions as `[{molecule, percentage, type}]` per strain

**Step 4: Run tests to verify they pass**

Run: `cd ~/cannalchemy && python -m pytest tests/test_api_strains.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/api/app.py tests/test_api_strains.py
git commit -m "feat(api): add strain, match, graph, and stats endpoints for Phase 3 UI"
```

---

## Task 2: Scaffold React Frontend

Create the Vite + React + Tailwind project structure with routing and design tokens.

**Files:**
- Create: `cannalchemy/frontend/package.json`
- Create: `cannalchemy/frontend/vite.config.js`
- Create: `cannalchemy/frontend/index.html`
- Create: `cannalchemy/frontend/src/main.jsx`
- Create: `cannalchemy/frontend/src/App.jsx`
- Create: `cannalchemy/frontend/src/styles/index.css` (Tailwind + design tokens)
- Create: `cannalchemy/frontend/src/lib/api.js` (API client)
- Create: `cannalchemy/frontend/src/components/Nav.jsx`
- Create: `cannalchemy/frontend/public/noise.svg` (grain texture)

**Step 1: Create package.json**

```json
{
  "name": "cannalchemy-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "d3": "^7.9.0",
    "lucide-react": "^0.564.0",
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "react-router-dom": "^7.13.0",
    "recharts": "^3.7.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.1.18",
    "@types/d3": "^7.4.3",
    "@vitejs/plugin-react": "^5.1.1",
    "tailwindcss": "^4.1.18",
    "vite": "^7.3.1"
  }
}
```

**Step 2: Create vite.config.js**

```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8421",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

**Step 3: Create index.html with Google Fonts**

Loads Playfair Display, DM Sans, IBM Plex Mono. Sets dark background color in `<style>` to prevent flash.

**Step 4: Create src/styles/index.css with design tokens**

All CSS custom properties from design doc. Tailwind `@import "tailwindcss"`. Custom utility classes for card treatment, grain overlay, scrollbar styling, focus rings, skeleton pulse animation.

**Step 5: Create src/lib/api.js**

API client with functions:
- `fetchStrains(q, type, limit)` → GET `/api/strains`
- `fetchStrain(name)` → GET `/api/strains/{name}`
- `matchEffects(effects, type)` → POST `/api/match`
- `fetchGraph()` → GET `/api/graph`
- `fetchGraphNode(nodeId)` → GET `/api/graph/{nodeId}`
- `fetchStats()` → GET `/api/stats`
- `fetchEffects()` → GET `/api/effects`
- `predictEffects(profile)` → POST `/api/predict`

Each wraps `fetch()` with error handling and JSON parsing.

**Step 6: Create App.jsx with routing**

```jsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Nav from "./components/Nav";
import Landing from "./pages/Landing";
import Explorer from "./pages/Explorer";
import StrainDetail from "./pages/StrainDetail";
import Compare from "./pages/Compare";
import Graph from "./pages/Graph";
import Quality from "./pages/Quality";

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/explore" element={<Explorer />} />
        <Route path="/strain/:name" element={<StrainDetail />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/graph" element={<Graph />} />
        <Route path="/quality" element={<Quality />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**Step 7: Create Nav component**

Nav bar with "⚗ CANNALCHEMY" logo (Playfair Display, gold, tracked), links to all pages. Mobile hamburger. Active link gold underline.

**Step 8: Create placeholder pages**

Each page file returns a simple `<div>` with the page name — will be filled in subsequent tasks.

**Step 9: Create noise.svg grain texture**

Small SVG pattern for the grain overlay.

**Step 10: Install dependencies and verify**

```bash
cd ~/cannalchemy/frontend && npm install
npm run dev
# Visit http://localhost:5173 — should see nav and placeholder pages
```

**Step 11: Commit**

```bash
cd ~/cannalchemy
git add frontend/
git commit -m "feat(frontend): scaffold React + Vite + Tailwind with Apothecary Lab design tokens"
```

---

## Task 3: Landing Page

Build the visually striking landing page.

**Files:**
- Modify: `cannalchemy/frontend/src/pages/Landing.jsx`
- Create: `cannalchemy/frontend/src/charts/HeroRadar.jsx` (animated background radar)

**Step 1: Build HeroRadar component**

D3-powered radar chart that slowly rotates (60s cycle). Low opacity (0.08), golden lines on dark. No data labels — purely decorative. Renders via `useRef` + D3 in `useEffect`.

**Step 2: Build Landing page**

Full-viewport hero section:
- Grain overlay background
- HeroRadar in absolute position behind content
- Centered layout: alchemist icon → title → subtitle → CTA → stats
- "Explore Effects →" link navigates to `/explore`
- Stats line fetched from `/api/stats` on mount (with fallback static values)
- Below fold: 3 feature cards with stagger fade-in (Intersection Observer)

**Step 3: Verify in browser**

```bash
cd ~/cannalchemy/frontend && npm run dev
# Visit http://localhost:5173 — landing should render with animated radar
```

**Step 4: Commit**

```bash
cd ~/cannalchemy
git add frontend/src/pages/Landing.jsx frontend/src/charts/HeroRadar.jsx
git commit -m "feat(frontend): add landing page with animated hero radar"
```

---

## Task 4: Terpene Radar Chart Component

The core reusable visualization. Used on Explorer (mini), Strain Detail (full), and Compare (overlaid).

**Files:**
- Create: `cannalchemy/frontend/src/charts/TerpeneRadar.jsx`

**Step 1: Build TerpeneRadar component**

Props:
- `data` — `[{name, percentage}]` array (non-zero terpenes only, sorted by %)
- `size` — number (80 for mini, 320 for full)
- `showLabels` — boolean (false for mini)
- `showTooltips` — boolean (true for full)
- `overlayData` — optional second `[{name, percentage}]` for comparison
- `overlayColor` — string (default `--green-bright`)

Implementation:
- D3 scales: `d3.scaleLinear()` for radius, `d3.scalePoint()` for angles
- Draw concentric hexagonal grid rings (3 levels: 33%, 66%, 100%)
- Draw axis spokes from center to each terpene
- Draw data polygon with `d3.lineRadial()` + area fill
- Data points as circles on polygon vertices
- Dominant terpene: thicker spoke, brighter label
- Labels: terpene name + percentage at each axis tip
- Tooltip on hover: name, %, one-line effect description
- Animation: polygon morphs in on mount (d3.transition, 500ms)
- Comparison overlay: second polygon in different color with legend

Terpene effect descriptions (hardcoded mapping):
```javascript
const TERPENE_EFFECTS = {
  myrcene: "Sedating, pain relief",
  limonene: "Mood elevation, stress relief",
  caryophyllene: "Anti-inflammatory, pain",
  pinene: "Alertness, memory",
  linalool: "Calming, anti-anxiety",
  terpinolene: "Uplifting, energizing",
  humulene: "Appetite suppressant",
  ocimene: "Anti-inflammatory, antiviral",
  bisabolol: "Soothing, anti-irritation",
  // ... all 21 terpenes
};
```

**Step 2: Test with hardcoded data**

Temporarily render in a test page with Blue Dream-like data:
```javascript
[{name: "myrcene", percentage: 0.45}, {name: "limonene", percentage: 0.32}, ...]
```

**Step 3: Verify both mini and full sizes render correctly**

```bash
cd ~/cannalchemy/frontend && npm run dev
# Check mini (80px): compact shape, no labels
# Check full (320px): labels, hover tooltips, dominant highlight
```

**Step 4: Commit**

```bash
cd ~/cannalchemy
git add frontend/src/charts/TerpeneRadar.jsx
git commit -m "feat(frontend): add TerpeneRadar D3 chart component (mini + full + overlay)"
```

---

## Task 5: Effect Probability Bars Component

Horizontal bar chart for predicted effect probabilities.

**Files:**
- Create: `cannalchemy/frontend/src/charts/EffectBars.jsx`

**Step 1: Build EffectBars component**

Props:
- `effects` — `[{name, category, probability, predicted}]`
- `compact` — boolean (fewer rows for strain cards)

Implementation:
- Sort by probability descending within groups: positive → medical → negative
- Each row: category dot (gold/blue/red) + effect name + bar + percentage
- Bar: CSS div with width = probability%, gradient from `--gold-dim` to `--gold`
- Negative effects: red gradient instead
- Medical effects: blue gradient
- 50% threshold dashed line (only in full mode)
- Hover: row expands to show receptor pathway summary (from CANONICAL_EFFECTS receptor_pathway field)
- Compact mode: top 5 effects only, no hover expand

**Step 2: Test with sample prediction data**

**Step 3: Commit**

```bash
cd ~/cannalchemy
git add frontend/src/charts/EffectBars.jsx
git commit -m "feat(frontend): add EffectBars probability chart component"
```

---

## Task 6: Strain Card and Effect Chip Components

Shared UI building blocks.

**Files:**
- Create: `cannalchemy/frontend/src/components/StrainCard.jsx`
- Create: `cannalchemy/frontend/src/components/EffectChip.jsx`
- Create: `cannalchemy/frontend/src/components/TypeBadge.jsx`

**Step 1: Build EffectChip**

Selectable pill button. Props: `name`, `category`, `selected`, `onToggle`.
- Three variants based on category (positive/negative/medical)
- Scale 1.03x on hover, spring animation on select
- Uses design token CSS variables

**Step 2: Build TypeBadge**

Small pill showing indica/sativa/hybrid. Props: `type`.
- Indica=green, Sativa=gold, Hybrid=cream-dim

**Step 3: Build StrainCard**

Card for search results. Props: `strain`, `score`, `onCompare`.
- Left: mini TerpeneRadar (80px) with strain composition data
- Right: name (Playfair), TypeBadge, top 3 effects as compact EffectBars
- Score: large % in IBM Plex Mono
- [Compare] button + link to `/strain/{name}`
- Fade-in animation (CSS)

**Step 4: Commit**

```bash
cd ~/cannalchemy
git add frontend/src/components/StrainCard.jsx frontend/src/components/EffectChip.jsx frontend/src/components/TypeBadge.jsx
git commit -m "feat(frontend): add StrainCard, EffectChip, TypeBadge components"
```

---

## Task 7: Explorer Page

The hero experience — "What do you want to feel?"

**Files:**
- Modify: `cannalchemy/frontend/src/pages/Explorer.jsx`

**Step 1: Build Explorer page**

Sections:
1. **Effect Picker**: Load effects from `/api/effects`. Render grouped EffectChips (Positive, Medical, Negative — negative collapsed by default). Multi-select state.
2. **Type Filter**: All/Indica/Sativa/Hybrid pill toggle. Sort dropdown.
3. **Results**: When effects selected, call `POST /api/match` with selected effects + type filter. Render result as list of StrainCards.
4. **Empty state**: When no effects selected, call `GET /api/strains?limit=12` for popular strains.
5. **Loading state**: Skeleton cards during fetch.

State management: `useState` for selectedEffects, selectedType, sortBy, results, loading.

**Step 2: Test the full flow**

Start API server: `cd ~/cannalchemy && uvicorn cannalchemy.api.app:app --port 8421`
Start frontend: `cd ~/cannalchemy/frontend && npm run dev`
1. Open `/explore`
2. Select "relaxed" + "pain"
3. Verify strain results appear ranked by score
4. Toggle type filter
5. Click strain card → navigates to `/strain/{name}`

**Step 3: Commit**

```bash
cd ~/cannalchemy
git add frontend/src/pages/Explorer.jsx
git commit -m "feat(frontend): add Explorer page with effect picker and strain matching"
```

---

## Task 8: Strain Detail Page

Deep dive into a single strain.

**Files:**
- Modify: `cannalchemy/frontend/src/pages/StrainDetail.jsx`
- Create: `cannalchemy/frontend/src/charts/PathwayDiagram.jsx`

**Step 1: Build PathwayDiagram component**

D3 force-directed graph showing this strain's molecule → receptor → effect paths.

Props: `pathways` — `[{molecule, receptor, ki_nm, affinity_score, action_type}]`, `effects` — predicted effect names.

Implementation:
- Build nodes and edges from pathways data
- Molecule nodes: hexagons (gold), Receptor nodes: circles (green), Effect nodes: rounded rects (cream)
- Edge thickness = affinity score (1-4px)
- D3 force simulation: `forceLink`, `forceManyBody`, `forceCenter`
- Hover node → highlight connected edges, dim rest
- Labels below nodes (IBM Plex Mono, 10px)
- Fixed size container (100% width, 400px height)
- Pan/zoom with d3.zoom

**Step 2: Build StrainDetail page**

`useParams()` to get strain name. Fetch `/api/strains/{name}` on mount.

Layout:
1. Header: strain name + TypeBadge + description
2. Two-column grid:
   - Left: Full TerpeneRadar (320px) + cannabinoid bars (simple CSS bars for THC, CBD, etc.)
   - Right: Full EffectBars
3. Full-width: PathwayDiagram
4. Bottom: "Similar Strains" — fetch `/api/strains?type={same_type}&limit=6`, render horizontal scroll of StrainCards

**Step 3: Verify**

Navigate to `/strain/Blue Dream` (or any known strain). Verify:
- Radar chart shows terpene profile
- Effect bars show predictions
- Pathway diagram renders with force layout
- Similar strains row loads

**Step 4: Commit**

```bash
cd ~/cannalchemy
git add frontend/src/pages/StrainDetail.jsx frontend/src/charts/PathwayDiagram.jsx
git commit -m "feat(frontend): add StrainDetail page with radar, effects, and pathway diagram"
```

---

## Task 9: Compare Page

Side-by-side strain comparison.

**Files:**
- Modify: `cannalchemy/frontend/src/pages/Compare.jsx`

**Step 1: Build Compare page**

State: `compareStrains` array (max 3), each with full profile data.

Sections:
1. **Strain selector**: Text input with autocomplete (calls `/api/strains?q=...` on keyup, debounced 300ms). Selected strains as removable chips. Max 3.
2. **Overlaid radar**: TerpeneRadar with `overlayData` props for comparison. Merge all terpenes from all strains as axes.
3. **Effect comparison**: Side-by-side columns, each with EffectBars for that strain.
4. **Key differences**: Auto-computed from effect predictions — find top 3 largest probability differences, render as text bullets.
5. **Chemistry table**: HTML table with molecule rows, strain columns, showing percentages with color coding (higher = brighter gold).

**Step 2: Support URL state**

Read/write compare strains to URL params: `/compare?strains=Blue+Dream,OG+Kush` — allows sharing links.

**Step 3: Verify**

Add 2-3 strains, verify overlaid radar, side-by-side effects, difference text.

**Step 4: Commit**

```bash
cd ~/cannalchemy
git add frontend/src/pages/Compare.jsx
git commit -m "feat(frontend): add Compare page with overlaid radar and effect diff"
```

---

## Task 10: Knowledge Graph Page

Full-screen interactive molecular network.

**Files:**
- Modify: `cannalchemy/frontend/src/pages/Graph.jsx`

**Step 1: Build Graph page**

Fetch `/api/graph` on mount (molecules + receptors + effects, no strain nodes).

Layout: Full viewport minus nav. Left sidebar (280px) + graph area.

Sidebar:
- Search input (filters visible nodes by name)
- Toggle buttons: Show Molecules / Show Receptors / Show Effects
- Selected node detail panel (click a node → show name, type, properties, connected nodes)
- Color legend

Graph (D3 canvas):
- `d3.forceSimulation` with `forceLink`, `forceManyBody(-100)`, `forceCenter`, `forceCollide(20)`
- Render on `<canvas>` for performance (est. ~100 nodes: 27 molecules + 6 receptors + 51 effects)
- Actually SVG is fine for ~100 nodes — use SVG for better interaction
- Node shapes by type: molecule=hexagon (gold), receptor=circle (green), effect=rounded-rect (cream)
- Edge: curved path, width = affinity_score for binds_to edges
- Click node → highlight connected subgraph (increase opacity of connected, decrease rest to 0.15)
- Double-click → zoom to node
- Pan/zoom with d3.zoom

**Step 2: Verify**

Open `/graph`. Verify:
- Force simulation settles in 2-3 seconds
- Nodes draggable
- Click highlights connections
- Sidebar search filters nodes
- Type toggles work

**Step 3: Commit**

```bash
cd ~/cannalchemy
git add frontend/src/pages/Graph.jsx
git commit -m "feat(frontend): add Knowledge Graph page with force-directed D3 visualization"
```

---

## Task 11: Data Quality Page

Dashboard showing data completeness and model performance.

**Files:**
- Modify: `cannalchemy/frontend/src/pages/Quality.jsx`

**Step 1: Build Quality page**

Fetch `/api/stats` on mount.

Layout:
1. **Stats cards row**: 5 cards (Total Strains, ML-Ready, Molecules, Effects, Avg Confidence). Each card: large number (IBM Plex Mono, gold), label below (DM Sans, cream-dim).
2. **Source breakdown**: Recharts `BarChart` showing effect_reports per source.
3. **Model performance**: Recharts `BarChart` of AUC by effect, sorted descending. Color by category.
4. **Confidence distribution**: Recharts `BarChart` as histogram of confidence scores.

Use Recharts for all charts — no D3 needed on this page. Style with Apothecary Lab colors using Recharts `fill`/`stroke` props.

**Step 2: Verify**

Open `/quality`. All charts render with real data from the API.

**Step 3: Commit**

```bash
cd ~/cannalchemy
git add frontend/src/pages/Quality.jsx
git commit -m "feat(frontend): add Data Quality dashboard with stats and Recharts"
```

---

## Task 12: Polish, Loading States, and Responsive Design

Final visual polish pass.

**Files:**
- Modify: Various frontend files

**Step 1: Add skeleton loading states**

Create `cannalchemy/frontend/src/components/Skeleton.jsx`:
- `SkeletonCard` — matches StrainCard dimensions
- `SkeletonRadar` — circle with pulse animation
- `SkeletonBars` — stacked rectangles

Use in Explorer (while matching), StrainDetail (while loading), Quality (while fetching stats).

**Step 2: Add error states**

Create `cannalchemy/frontend/src/components/ErrorCard.jsx`:
- Red border card with error message + "Retry" button
- Use in all pages where API calls can fail

**Step 3: Responsive design pass**

- Landing: stack feature cards vertically on mobile
- Explorer: effect chips wrap, strain cards full-width on mobile
- StrainDetail: stack chemistry/effects vertically on mobile, reduce radar to 240px
- Compare: single-column on mobile
- Graph: sidebar becomes bottom drawer on mobile
- Nav: hamburger menu on < 768px

**Step 4: Scrollbar and focus styling**

Apply thin scrollbar styling, gold focus rings, smooth transitions as specified in design doc.

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add frontend/
git commit -m "feat(frontend): add loading states, error handling, responsive design, polish"
```

---

## Task 13: Docker Deployment

Package everything for production.

**Files:**
- Create: `cannalchemy/Dockerfile`
- Create: `cannalchemy/docker-compose.yml`
- Create: `cannalchemy/frontend/nginx.conf`

**Step 1: Create nginx.conf**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://api:8421/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**Step 2: Create Dockerfile (multi-stage)**

```dockerfile
# Stage 1: Build frontend
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python API
FROM python:3.12-slim AS api
WORKDIR /app
COPY pyproject.toml .
COPY cannalchemy/ cannalchemy/
COPY data/ data/
RUN pip install --no-cache-dir ".[api,ml]"
CMD ["uvicorn", "cannalchemy.api.app:app", "--host", "0.0.0.0", "--port", "8421"]

# Stage 3: Frontend nginx
FROM nginx:alpine AS frontend
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
```

**Step 3: Create docker-compose.yml**

```yaml
version: "3.8"
services:
  api:
    build:
      context: .
      target: api
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  frontend:
    build:
      context: .
      target: frontend
    ports:
      - "8422:80"
    depends_on:
      - api
    restart: unless-stopped
```

**Step 4: Build and test**

```bash
cd ~/cannalchemy
docker compose build
docker compose up -d
# Visit http://localhost:8422 — full app should work
```

**Step 5: Add Cloudflare tunnel route**

Update `~/cloudflared-config.yml` to route `cannalchemy.library.icu` → `http://localhost:8422`.

**Step 6: Commit**

```bash
cd ~/cannalchemy
git add Dockerfile docker-compose.yml frontend/nginx.conf
git commit -m "feat: add Docker deployment for Cannalchemy frontend + API"
```

---

## Task 14: Update Documentation and SESSION-LOG

Final documentation pass.

**Files:**
- Modify: `docs/SESSION-LOG.md`
- Modify: `CLAUDE.md` (if Cannalchemy gets its own)

**Step 1: Update SESSION-LOG with Phase 3 section**

Add Phase 3 section documenting:
- All 6 pages built
- Design system choices (Apothecary Lab)
- New API endpoints
- Component inventory
- Docker deployment
- Test count update

**Step 2: Verify all tests pass**

```bash
cd ~/cannalchemy && python -m pytest tests/ -v
```

**Step 3: Final commit**

```bash
cd ~/cannalchemy
git add docs/SESSION-LOG.md
git commit -m "docs: add Phase 3 completion to session log"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Extend Backend API (6 endpoints) | `api/app.py`, `tests/test_api_strains.py` |
| 2 | Scaffold Frontend (React+Vite+Tailwind) | `frontend/` directory |
| 3 | Landing Page | `pages/Landing.jsx`, `charts/HeroRadar.jsx` |
| 4 | Terpene Radar Chart | `charts/TerpeneRadar.jsx` |
| 5 | Effect Probability Bars | `charts/EffectBars.jsx` |
| 6 | Strain Card + Effect Chip | `components/StrainCard.jsx`, `EffectChip.jsx`, `TypeBadge.jsx` |
| 7 | Explorer Page | `pages/Explorer.jsx` |
| 8 | Strain Detail Page | `pages/StrainDetail.jsx`, `charts/PathwayDiagram.jsx` |
| 9 | Compare Page | `pages/Compare.jsx` |
| 10 | Knowledge Graph Page | `pages/Graph.jsx` |
| 11 | Data Quality Page | `pages/Quality.jsx` |
| 12 | Polish + Loading + Responsive | Various |
| 13 | Docker Deployment | `Dockerfile`, `docker-compose.yml`, `nginx.conf` |
| 14 | Documentation | `SESSION-LOG.md` |
