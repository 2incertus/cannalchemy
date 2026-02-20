# Phase 5: LLM Explanation Layer — Design Document

**Date:** 2026-02-20
**Status:** Approved
**Author:** Mathias + Claude

## Overview

Add a pluggable LLM explanation layer that translates ML predictions into human-readable prose. Two surfaces: full 2-4 sentence explanations on strain detail pages, and 1-line summaries on Explorer match result cards.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM backend | Pluggable: Z.AI (glm-4.7) primary, Ollama (llama3.2) fallback | Best quality by default, local fallback for resilience |
| Generation strategy | On-demand + SQLite cache | No upfront cost, fast repeat visits, cache invalidates on model version change |
| Tone | Knowledgeable friend | Accessible but scientific — uses receptor/terpene names naturally |
| Failure mode | Graceful degradation | Page works without explanation section; no error banners |
| Placement | Strain Detail (full) + Explorer cards (1-liner) | Full context on detail, quick insight on browse |

## Architecture

### Backend Module: `cannalchemy/explain/llm.py`

Pluggable LLM client with provider fallback chain:

```python
class LLMClient:
    """Pluggable LLM client. Tries primary (Z.AI), falls back to secondary (Ollama)."""

    def explain_strain(self, strain_data: dict) -> str | None:
        """2-4 sentence explanation for strain detail page."""

    def summarize_strain(self, strain_data: dict) -> str | None:
        """1-line summary (~20 words) for match result cards."""
```

**Provider protocols:**
- Z.AI: Anthropic-compatible messages API (`POST /v1/messages`)
- Ollama: Native generate API (`POST /api/generate`)

**Configuration (env vars):**
```
CANNALCHEMY_LLM_PRIMARY_URL=https://api.z.ai/api/anthropic/v1/messages
CANNALCHEMY_LLM_PRIMARY_MODEL=glm-4.7
CANNALCHEMY_LLM_PRIMARY_KEY=<key>
CANNALCHEMY_LLM_FALLBACK_URL=http://host.docker.internal:11434
CANNALCHEMY_LLM_FALLBACK_MODEL=llama3.2
```

### Cache: `strain_explanations` table

```sql
CREATE TABLE strain_explanations (
    strain_id INTEGER NOT NULL,
    explanation_type TEXT NOT NULL,  -- 'full' or 'summary'
    content TEXT NOT NULL,
    model_version TEXT NOT NULL,     -- ML model version; old entries ignored on change
    llm_provider TEXT NOT NULL,      -- 'zai' or 'ollama'
    created_at TEXT NOT NULL,
    PRIMARY KEY (strain_id, explanation_type, model_version)
);
```

Cache hit: return immediately. Cache miss: generate, store, return. Model version change: old cache ignored, new entry created on next request.

### API Endpoints

**`GET /strains/{name}/explain`** — Full explanation for strain detail.
```json
{"explanation": "Blue Dream's terpene profile is dominated by...", "provider": "zai", "cached": true}
```
Returns `{"explanation": null}` if LLM unavailable.

**`POST /match`** — Existing endpoint gains optional `explain: bool` field (default false). When true, each result includes a `summary` field. Generated on cache miss, cached for reuse.

### Data Flow

```
Strain Detail Page:
  Frontend: fetchStrain(name)           → instant (existing)
  Frontend: fetchExplanation(name)      → async, non-blocking
    API: check strain_explanations cache
      HIT  → return cached
      MISS → Z.AI (10s timeout)
        success → cache + return
        fail    → Ollama (15s timeout)
          success → cache + return
          fail    → return null
    Frontend: show "AI Analysis" card or hide section

Explorer Match Results:
  Frontend: matchEffects(effects, type, limit, explain=true)
    API: for each result strain, check summary cache
      HIT  → inline summary
      MISS → generate + cache (batch)
    Frontend: show summary line on StrainCard or omit
```

## Prompt Engineering

### Full Explanation (Strain Detail)

```
You are a cannabis scientist explaining strain effects to an informed consumer.
Given this strain's chemistry and predicted effects, explain WHY these effects
occur at the molecular level. Be specific about which terpenes/cannabinoids
drive which effects and mention receptor interactions when available.

Strain: {name} ({type})
Terpenes: {top 5 terpenes with %}
Cannabinoids: {THC, CBD, etc with %}
Top predicted effects: {top 5 with probability and confidence}
Receptor pathways: {molecule -> receptor pairs}

Write 2-4 sentences. Use an accessible but scientific tone — like a well-informed
budtender with a biochemistry background.
```

### Summary (Explorer Cards)

```
Summarize this strain's key effect in one sentence (max 20 words).
Strain: {name}, dominant terpene: {top terpene}, top effect: {top effect} ({prob}%)
```

## Frontend Integration

### StrainDetail.jsx

After strain data loads, fire async `fetchExplanation(name)`. Display in an "AI Analysis" card below the pathway diagram:
- Loading: subtle shimmer placeholder
- Success: fade in the explanation text with provider badge
- Failure/null: hide the section entirely (graceful degradation)

### StrainCard.jsx

When `strain.summary` is present (from match with explain=true), show as a small italic line below the strain name. When absent, card renders identically to current behavior.

### Explorer.jsx

Add toggle: "Show AI summaries" (off by default). When on, pass `explain: true` to match endpoint. Keeps default performance unchanged.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Z.AI timeout (>10s) | Fall back to Ollama |
| Ollama timeout (>15s) | Return null |
| Z.AI 429 rate limit | Skip Z.AI for 60s, use Ollama |
| Empty/too-long/refusal response | Return null, don't cache |
| DB write failure | Log warning, return explanation uncached |
| Both providers down | Return null, frontend hides section |

## Docker Changes

Add to `docker-compose.yml`:
```yaml
environment:
  - CANNALCHEMY_LLM_PRIMARY_URL
  - CANNALCHEMY_LLM_PRIMARY_MODEL
  - CANNALCHEMY_LLM_PRIMARY_KEY
  - CANNALCHEMY_LLM_FALLBACK_URL
  - CANNALCHEMY_LLM_FALLBACK_MODEL
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## Testing

- Unit tests: `LLMClient` with mocked HTTP responses (both providers, fallback logic, timeouts)
- Unit tests: cache hit/miss/invalidation logic
- Integration test: `/strains/{name}/explain` endpoint (mocked LLM)
- E2E: Playwright test verifying explanation section appears on strain detail page
- No tests requiring actual LLM API calls

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `cannalchemy/explain/llm.py` | Create | LLM client with provider fallback |
| `cannalchemy/api/app.py` | Modify | Add `/strains/{name}/explain` endpoint, add `explain` to match |
| `frontend/src/lib/api.js` | Modify | Add `fetchExplanation()` function |
| `frontend/src/pages/StrainDetail.jsx` | Modify | Add AI Analysis section |
| `frontend/src/components/StrainCard.jsx` | Modify | Add summary line |
| `frontend/src/pages/Explorer.jsx` | Modify | Add AI summaries toggle |
| `docker-compose.yml` | Modify | Add env vars + extra_hosts |
| `tests/test_explain.py` | Create | LLM client + cache tests |
| `tests/test_api_explain.py` | Create | Explain endpoint integration tests |
| `frontend/e2e/explain.spec.js` | Create | E2E test for explanation UI |
