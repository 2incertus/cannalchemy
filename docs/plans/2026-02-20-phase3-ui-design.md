# Phase 3: Visualization + UI — "The Apothecary Lab"

## Overview

Cannalchemy's frontend is a standalone React application serving as a visual interface to the XGBoost effect prediction engine, knowledge graph, and 5,017-strain chemical database. The aesthetic is **dark botanical science** — old-world apothecary meets modern data visualization.

**Target audience**: Cannabis enthusiasts who know strain names and effects but not pharmacology. Approachable design with optional deep-dive layers into molecular pathways.

## Architecture

```
cannalchemy/
├── frontend/              ← NEW (React + Vite + Tailwind + D3)
│   ├── src/
│   │   ├── components/    # Shared UI components
│   │   ├── pages/         # 6 route pages
│   │   ├── charts/        # D3 + Recharts visualizations
│   │   ├── hooks/         # React hooks (useApi, useCompare)
│   │   ├── lib/           # API client, utils
│   │   └── styles/        # Global CSS, design tokens
│   ├── public/            # Static assets (noise texture, favicon)
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
├── cannalchemy/api/       ← EXTEND (new endpoints)
│   └── app.py
├── Dockerfile             ← NEW (multi-stage: build frontend + serve API)
└── docker-compose.yml     ← NEW
```

### Deployment

| Service | Port | URL |
|---------|------|-----|
| Frontend (nginx) | 8422 | cannalchemy.library.icu |
| API (uvicorn) | 8421 | cannalchemy.library.icu/api |

Single `docker-compose.yml`:
- **frontend**: nginx:alpine serving built React, proxying `/api` → backend
- **api**: Python 3.12 + uvicorn serving FastAPI, reading SQLite DB + trained model

### API Endpoints (New)

Extend `cannalchemy/api/app.py`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/strains` | Search/list strains. Query: `?q=blue&type=hybrid&limit=50` |
| GET | `/api/strains/{name}` | Full strain profile: compositions, predicted effects, pathways |
| POST | `/api/match` | Find strains matching desired effects. Body: `{effects: ["relaxed","pain"], type: "any"}` |
| GET | `/api/graph` | Knowledge graph data: all nodes + edges for D3 force layout |
| GET | `/api/graph/{node_id}` | Subgraph centered on a specific node |
| GET | `/api/stats` | Data quality stats: coverage, source counts, confidence distribution |
| Existing | `/api/predict` | Predict effects from chemical profile |
| Existing | `/api/effects` | List all effects |
| Existing | `/api/features` | List input features |
| Existing | `/api/health` | Health check |

## Visual Design System

### Color Palette

```css
:root {
  --bg-void:      #080C10;    /* deepest background */
  --bg-dark:      #0D1117;    /* page background */
  --bg-card:      #151D14;    /* card surfaces — dark sage tint */
  --bg-elevated:  #1A2F23;    /* elevated panels, hover states */
  --border:       #2A3A2E;    /* subtle borders, dividers */

  --gold:         #D4A843;    /* primary accent — amber gold */
  --gold-dim:     #8B7435;    /* secondary gold for less emphasis */
  --gold-glow:    rgba(212, 168, 67, 0.12); /* gold glow/shadows */

  --green:        #5C8A4D;    /* terpene/botanical accent */
  --green-bright: #7CB668;    /* chart highlights, success */

  --cream:        #E8DCC8;    /* primary text */
  --cream-dim:    #A09482;    /* secondary/muted text */
  --cream-faint:  #605848;    /* disabled, subtle labels */

  --red:          #C45C4A;    /* negative effects, warnings */
  --blue:         #4A7CB6;    /* medical effects */
}
```

### Typography

| Role | Font | Usage |
|------|------|-------|
| Display | Playfair Display (serif) | Headings, strain names, hero text |
| Body | DM Sans (geometric sans) | UI text, descriptions, navigation |
| Data | IBM Plex Mono (monospace) | Percentages, scores, chart labels |

All loaded via Google Fonts. Fallbacks: Georgia → serif, system-ui → sans-serif, monospace.

### Texture & Atmosphere

- **Grain overlay**: SVG noise pattern at 3-5% opacity over `--bg-dark` background
- **Card treatment**: 1px `--border` border + inner box-shadow of `--gold-glow`
- **Hover states**: Background transitions to `--bg-elevated`, border to `--gold-dim`
- **Focus rings**: 2px `--gold` outline with 4px offset
- **Scrollbar**: Thin, styled with `--bg-elevated` track and `--gold-dim` thumb
- **Transitions**: 200ms ease-out for colors, 300ms for transforms

## Components

### Effect Chips

Selectable pill buttons for choosing desired effects.

- **Default**: `--bg-card` background, 1px `--border` border, `--cream-dim` text
- **Hover**: `--bg-elevated` background, `--gold-dim` border
- **Selected positive**: `--gold` at 15% bg, `--gold` border, `--gold` text
- **Selected negative**: `--red` at 15% bg, `--red` border, `--red` text
- **Selected medical**: `--blue` at 15% bg, `--blue` border, `--blue` text
- **Animation**: Scale to 1.03x on hover, spring animation on select

### Terpene Radar Chart (D3.js)

Spider/radar chart showing terpene fingerprint of a strain. **Clarity is the #1 priority** — users should instantly understand which terpenes dominate and how they compare.

- **Axes**: Show only terpenes present in the strain (typically 5-8), ordered clockwise by percentage. Skip zero-value terpenes to avoid clutter.
- **Labels**: Terpene name + actual percentage next to each axis tip (e.g., "myrcene 0.45%"). IBM Plex Mono, `--cream` for dominant, `--cream-dim` for secondary. Large enough to read (12px min on full chart).
- **Grid**: Concentric hexagonal rings in `--border` color (3 rings: 33%, 66%, 100%). Rings labeled with percentage at one axis only (not all) to reduce noise.
- **Area fill**: `--gold` at 15% opacity
- **Stroke**: `--gold` at full opacity, 2px
- **Data points**: 6px circles at each axis value, `--gold` fill with `--gold-glow` shadow. **Hover**: tooltip with terpene name, percentage, and one-line effect summary (e.g., "myrcene 0.45% — sedating, pain relief").
- **Comparison mode**: Second polygon in `--green-bright`, third in `--blue`. Legend below chart mapping colors to strain names.
- **Mini version**: 80×80px for strain cards, no labels, just the polygon shape with area fill. Recognizable at a glance as a terpene fingerprint.
- **Full version**: 320×320px on Strain Detail and Compare pages. Always includes labels and hover tooltips.
- **Animation**: Polygon morphs in on mount (500ms spring). Data points appear with 50ms stagger.
- **Dominant indicator**: The axis with the highest value has a slightly thicker spoke line and brighter label — makes the dominant terpene instantly obvious.

### Effect Probability Bars (Recharts)

Horizontal bar chart showing predicted effect probabilities.

- **Bar**: Gradient from `--gold-dim` (left) to `--gold` (right)
- **Width**: Proportional to probability (0-100%)
- **Label**: Effect name left-aligned, percentage right-aligned
- **Category badge**: Small 6px circle (gold/red/blue) before effect name
- **AUC indicator**: Thin `--cream-faint` line at model AUC position
- **Threshold line**: Dashed vertical line at 50% (prediction threshold)
- **Hover**: Expand row, show receptor pathway summary text
- **Negative effects**: Bar uses `--red` gradient, sorted separately below positives

### Pathway Diagram (D3.js Force-Directed)

Interactive graph showing Molecule → Receptor → Effect connections.

- **Molecule nodes**: Hexagons, 20px, `--gold` stroke, `--bg-card` fill
- **Receptor nodes**: Circles, 16px, `--green` stroke, `--bg-card` fill
- **Effect nodes**: Rounded rectangles, `--cream` stroke, `--bg-card` fill
- **Edges**: Curved paths, thickness = binding affinity (1-4px)
- **Edge color**: `--border` default, `--gold` on hover/highlight
- **Labels**: Below nodes, IBM Plex Mono, 10px
- **Interaction**: Hover node → highlight all connected paths, dim others
- **Animation**: Particles flowing along edges on hover (tiny gold dots)
- **Pan/zoom**: D3 zoom behavior, scroll + drag

### Strain Card

Card component for search results.

- **Layout**: Left column (mini radar 80px), right column (name, type, top effects)
- **Background**: `--bg-card` with `--gold-glow` box-shadow
- **Border**: 1px `--border`, `--gold-dim` on hover
- **Strain name**: Playfair Display, `--cream`
- **Type badge**: Small pill (Indica=`--green`, Sativa=`--gold`, Hybrid=`--cream-dim`)
- **Match score**: Large percentage in IBM Plex Mono, `--gold`
- **Actions**: [Compare] button, [→] detail link
- **Animation**: Fade-in with 50ms stagger per card

### Navigation

Minimal top bar.

- **Logo**: "⚗ CANNALCHEMY" in Playfair Display, tracked 0.15em, `--gold`
- **Links**: DM Sans, `--cream-dim`, `--cream` on hover, `--gold` underline on active
- **Mobile**: Hamburger menu, full-screen overlay with `--bg-dark` backdrop
- **Height**: 64px, `--bg-void` background, 1px `--border` bottom

## Pages

### Page 0: Landing (`/`)

The first impression. Visually striking, minimal content, clear CTA.

**Hero section** (full viewport):
- Centered content on `--bg-dark` with grain overlay
- Animated terpene radar chart in background (slowly rotating, 60s cycle, very low opacity)
- "⚗" alchemist icon, subtle gold glow animation
- "CANNALCHEMY" in Playfair Display, 3rem, letter-spacing 0.2em, `--gold`
- "The science behind how you feel" in DM Sans italic, `--cream-dim`
- "Explore Effects →" CTA button: `--gold` border, transparent bg, gold text, fills on hover
- Stats line: "5,017 strains · 27 molecules · 51 effects" in IBM Plex Mono, `--cream-faint`

**Feature cards** (below fold, 3-column grid):
1. **Predict** — "Enter chemistry, see effects" with mini probability bar illustration
2. **Compare** — "Side-by-side strain analysis" with overlaid radar mini illustration
3. **Pathways** — "Trace molecule to effect" with mini pathway diagram illustration

Cards fade in with stagger animation on scroll into view.

### Page 1: Explorer (`/explore`)

The hero experience. "What do you want to feel?"

**Sections** (top to bottom):
1. **Effect picker**: "What do you want to feel?" heading (Playfair, gold). Grid of Effect Chips grouped by category (Positive, Medical, Negative—collapsed by default). Multi-select.
2. **Filters**: Type filter (All/Indica/Sativa/Hybrid pills), sort dropdown (Best Match/Name/Type)
3. **Results**: "N Matching Strains" header. List of Strain Cards. Infinite scroll or "Load More".
4. **Empty state**: When no effects selected, show popular strains or "Select effects to find your match"

**Match scoring**: For each strain, POST to `/api/predict` with its chemistry, then score = average probability across selected effects. Sort descending.

**Alternative approach**: Use new `POST /api/match` endpoint that does this server-side for better performance.

### Page 2: Strain Detail (`/strain/:name`)

Deep dive into a single strain.

**Sections**:
1. **Header**: Strain name (Playfair, 2rem), type badge, description if available
2. **Chemistry panel** (left half): Full Terpene Radar Chart + cannabinoid breakdown (THC/CBD/etc. as horizontal bars)
3. **Effects panel** (right half): Effect Probability Bars from model prediction
4. **Pathways** (full width): Force-directed pathway diagram showing this strain's molecules → receptors → effects
5. **Similar strains** (bottom): Horizontal scroll of Strain Cards for chemically similar strains

### Page 3: Compare (`/compare`)

Side-by-side strain comparison. Supports 2-3 strains.

**Sections**:
1. **Strain selector**: Search/autocomplete to add strains (max 3). Each shows as a removable chip.
2. **Overlaid radar**: Single radar chart with multiple strain polygons (gold, green, blue)
3. **Effect comparison**: Side-by-side Effect Probability Bars per strain
4. **Key differences**: Auto-generated text highlighting biggest differences ("OG Kush is 5% more relaxing but 25% less focused")
5. **Chemistry table**: Molecule-by-molecule comparison table with per-strain percentages

### Page 4: Knowledge Graph (`/graph`)

Full-screen interactive molecular network.

**Layout**: Full viewport, sidebar on left (280px).

**Sidebar**:
- Search input (filter nodes by name)
- Node type toggles: Molecules / Receptors / Effects
- Selected node details panel (appears on click)
- Legend with node shapes/colors

**Graph area**:
- D3 force-directed simulation with all nodes
- Color-coded by type (gold hexagons, green circles, cream rects)
- Click node → highlight connected subgraph, show details in sidebar
- Double-click → zoom to node and expand neighbors
- Pan/zoom with scroll + drag
- Performance: Use canvas renderer for >500 nodes, SVG for smaller subgraphs

### Page 5: Data Quality (`/quality`)

Dashboard showing data completeness and model performance.

**Cards row** (top):
- Total strains, ML-ready strains, molecules, effects, average confidence

**Charts**:
1. **Coverage heatmap**: Recharts heatmap showing molecule × source coverage
2. **Source breakdown**: Bar chart of effect_reports per source (allbud, leafly, leafly-reviews, cannlytics)
3. **Confidence distribution**: Histogram of confidence scores across all strain-effect pairs
4. **Model performance**: AUC by effect bar chart, sorted descending
5. **Missing data**: Table highlighting strains/molecules with lowest coverage

## Error & Loading States

- **Loading**: Skeleton screens matching card/chart layouts, pulsing `--bg-elevated` on `--bg-card`
- **Error**: Red-bordered card with error message, "Retry" button
- **Empty results**: Illustrated empty state with suggestion text
- **API unreachable**: Full-page notice with health check status

## Accessibility

- All interactive elements keyboard-navigable
- Focus rings visible (2px `--gold` outline)
- Chart data accessible via screen-reader-friendly tables (hidden visually)
- Color not sole indicator — shapes/labels always present
- Min contrast ratio 4.5:1 for body text (`--cream` on `--bg-dark` = 9.2:1)

## Performance

- Code-split by route (React.lazy + Suspense)
- D3 charts lazy-loaded (only on pages that use them)
- Knowledge graph uses canvas for >500 nodes
- API responses cached client-side (5-minute TTL)
- Images: none needed (all data-driven SVG/canvas)
- Target: <3s first contentful paint, <100ms chart interaction

## Dependencies

```json
{
  "dependencies": {
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "react-router-dom": "^7.13.0",
    "recharts": "^3.7.0",
    "d3": "^7.9.0",
    "lucide-react": "^0.564.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^5.1.1",
    "vite": "^7.3.1",
    "tailwindcss": "^4.1.18",
    "@tailwindcss/vite": "^4.1.18"
  }
}
```

## Verification

1. `cd cannalchemy/frontend && npm run dev` — dev server with hot reload
2. `cd cannalchemy && uvicorn cannalchemy.api.app:app --port 8421` — API server
3. Visit `http://localhost:5173` — all 6 pages render
4. Test predictions on Explorer page — select effects, see ranked results
5. Test strain detail — radar chart renders, pathways diagram loads
6. Test compare — overlay radar works with 2-3 strains
7. Test knowledge graph — force simulation runs, click/zoom works
8. `docker compose up --build` — production build + nginx serving

## Sources & Inspiration

- [Leafly visual system](https://www.leafly.com/news/cannabis-101/find-which-weed-strain-is-best-for-you) — Shape + color encoding for cannabinoids/terpenes
- [Strain Data Project compass](https://straindataproject.org/) — Radar chart for terpene profiles, 6-category color system
- [Goldleaf terpene art prints](https://www.amazon.com/Primary-Terpenes-Cannabis-Marijuana-Infographic/dp/B0777QP32X) — Botanical science illustration aesthetic
- [Apothecary design trend](https://www.housedigest.com/1233166/the-apothecary-aesthetic-thats-equal-parts-moody-and-charming/) — Dark, moody, botanical color palettes and typography
- [React Graph Gallery radar charts](https://www.react-graph-gallery.com/radar-chart) — D3 + React radar implementation patterns
- [D3 force-directed graphs](https://d3-graph-gallery.com/spider) — Force simulation patterns for knowledge graphs
- [Awwwards data visualization](https://www.awwwards.com/websites/data-visualization/) — Best-in-class dashboard design examples
- [Dribbble dark dashboards](https://dribbble.com/tags/dark-dashboard) — Dark theme data visualization inspiration
