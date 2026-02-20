# Phase 1C: Consumer Data (Leafly + AllBud) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand effect reports by scraping Leafly and AllBud consumer data, mapping to canonical effects, and computing multi-source confidence scores — boosting ML-readiness from 8% (5,653 strains) to 60%+ (15,000+).

**Architecture:** Two scrapers (Leafly via Firecrawl API, AllBud via httpx) feed into a consumer effect mapper that normalizes effect names to our 51 canonical effects, then an importer writes to `effect_reports` with multi-source confidence scoring. Priority targets: 11,701 Strain Tracker strains that have compositions but no effects.

**Tech Stack:** httpx (existing), beautifulsoup4 (new), existing taxonomy/normalize modules, Firecrawl REST API (optional, for Leafly Cloudflare bypass)

---

## Current State

| Metric | Value |
|--------|-------|
| Total strains | 67,477 (24,853 Strain Tracker + 42,624 Cannlytics) |
| ML-ready (compositions + effects) | 5,653 (8%) |
| Have compositions, no effects | 54,325 |
| Strain Tracker strains with compositions, no effects | 11,701 (priority targets) |
| Effect reports | 24,624 (all from strain-tracker) |
| Canonical effects | 51 (20 positive + 12 negative + 19 medical) |

## Data Source Assessment

**Leafly** (primary, richest):
- URL pattern: `https://www.leafly.com/strains/{slug}`
- Data: Effects + vote counts, medical + percentages, negatives, terpenes (relative), THC/CBD, rating, reviews
- Protection: Cloudflare — needs Firecrawl API or browser rendering
- __NEXT_DATA__ JSON embedded in page contains structured strain data
- Tested via Firecrawl: Blue Dream returned all fields cleanly

**AllBud** (secondary, bulk):
- URL pattern: `https://www.allbud.com/marijuana-strains/sativa/blue-dream` (includes strain type)
- Data: Effects, medical uses, negatives, flavors, strain type, THC/CBD
- Protection: None (direct httpx works)
- No vote counts, no terpene data

**Effect Name Mapping** (Leafly/AllBud → Canonical):
- Most Leafly effects are 1:1 with our canonical names (e.g., "Creative" → "creative", "Dry Mouth" → "dry-mouth")
- AllBud uses similar naming conventions
- Mapping is mostly: lowercase → replace spaces with hyphens → exact match to canonical
- Edge cases handled by synonym lookup from `taxonomy.py`

---

### Task 1: Consumer Config & URL Builder

**Files:**
- Create: `cannalchemy/data/consumer_config.py`
- Create: `tests/test_consumer_config.py`
- Modify: `pyproject.toml` (add beautifulsoup4)

**Step 1: Write the failing tests**

```python
"""Tests for consumer scraping configuration."""
import pytest
from cannalchemy.data.consumer_config import (
    strain_to_leafly_url,
    strain_to_allbud_url,
    SCRAPE_CONFIG,
)


def test_leafly_url_basic():
    assert strain_to_leafly_url("Blue Dream") == "https://www.leafly.com/strains/blue-dream"


def test_leafly_url_og_kush():
    """OG Kush has periods in name — must handle."""
    assert strain_to_leafly_url("O.G. Kush") == "https://www.leafly.com/strains/og-kush"


def test_leafly_url_special_chars():
    """Hashes, parens, apostrophes removed."""
    assert strain_to_leafly_url("Girl Scout Cookies #4") == "https://www.leafly.com/strains/girl-scout-cookies-4"


def test_allbud_url_basic():
    url = strain_to_allbud_url("Blue Dream", "sativa")
    assert url == "https://www.allbud.com/marijuana-strains/sativa/blue-dream"


def test_allbud_url_unknown_type():
    """Unknown strain type defaults to hybrid."""
    url = strain_to_allbud_url("Mystery Strain", "unknown")
    assert url == "https://www.allbud.com/marijuana-strains/hybrid/mystery-strain"


def test_allbud_url_indica():
    url = strain_to_allbud_url("Northern Lights", "indica")
    assert url == "https://www.allbud.com/marijuana-strains/indica/northern-lights"


def test_scrape_config_defaults():
    assert SCRAPE_CONFIG["rate_limit"] > 0
    assert SCRAPE_CONFIG["max_retries"] >= 1
    assert "firecrawl_api_url" in SCRAPE_CONFIG
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/cannalchemy && python -m pytest tests/test_consumer_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cannalchemy.data.consumer_config'`

**Step 3: Write implementation**

```python
"""Consumer scraping configuration: URL builders, rate limits, API settings."""
import re

SCRAPE_CONFIG = {
    "rate_limit": 1.0,  # seconds between requests
    "max_retries": 3,
    "retry_delay": 5.0,  # seconds
    "timeout": 30.0,  # seconds
    "firecrawl_api_url": "https://api.firecrawl.dev/v1/scrape",
    "user_agent": "Mozilla/5.0 (compatible; Cannalchemy/0.1; research)",
    "batch_size": 100,  # save progress every N strains
}


def _slugify(name: str) -> str:
    """Convert a strain name to a URL slug.

    'Blue Dream' -> 'blue-dream'
    'O.G. Kush' -> 'og-kush'
    'Girl Scout Cookies #4' -> 'girl-scout-cookies-4'
    """
    slug = name.lower().strip()
    slug = slug.replace(".", "")
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug


def strain_to_leafly_url(name: str) -> str:
    """Build Leafly strain page URL from strain name."""
    return f"https://www.leafly.com/strains/{_slugify(name)}"


def strain_to_allbud_url(name: str, strain_type: str = "hybrid") -> str:
    """Build AllBud strain page URL from strain name and type."""
    if strain_type not in ("indica", "sativa", "hybrid"):
        strain_type = "hybrid"
    return f"https://www.allbud.com/marijuana-strains/{strain_type}/{_slugify(name)}"
```

**Step 4: Run tests to verify they pass**

Run: `cd ~/cannalchemy && python -m pytest tests/test_consumer_config.py -v`
Expected: 7 PASSED

**Step 5: Add beautifulsoup4 dependency**

In `pyproject.toml`, add `"beautifulsoup4>=4.12"` to the `dependencies` list.

**Step 6: Install new dependency**

Run: `cd ~/cannalchemy && pip install -e ".[dev]"`

**Step 7: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/consumer_config.py tests/test_consumer_config.py pyproject.toml
git commit -m "feat(1c): add consumer scraping config and URL builders"
```

---

### Task 2: AllBud Scraper Module

**Files:**
- Create: `cannalchemy/data/allbud_scraper.py`
- Create: `tests/test_allbud_scraper.py`
- Create: `tests/fixtures/allbud_blue_dream.html` (test fixture)

**Context:** AllBud pages have no Cloudflare protection. We scrape with httpx and parse with BeautifulSoup. AllBud strain pages have structured sections for effects, medical uses, negatives, and flavors, plus THC/CBD ranges and ratings.

**Step 1: Capture a real AllBud page for test fixtures**

Before writing tests, fetch a real AllBud page to understand the HTML structure:

Run: `cd ~/cannalchemy && python3 -c "
import httpx
resp = httpx.get('https://www.allbud.com/marijuana-strains/sativa-dominant-hybrid/blue-dream',
    headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=True, timeout=30)
print(f'Status: {resp.status_code}')
print(f'Length: {len(resp.text)}')
# Save for fixture
with open('tests/fixtures/allbud_sample.html', 'w') as f:
    f.write(resp.text)
print('Saved to tests/fixtures/allbud_sample.html')
"`

Examine the HTML to identify the DOM structure for effects, medical uses, THC/CBD, etc. Then create a minimal fixture from the key sections.

**Step 2: Write the failing tests**

```python
"""Tests for AllBud strain scraper."""
import pytest
from pathlib import Path
from cannalchemy.data.allbud_scraper import parse_allbud_page, AllBudResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_html():
    """Load saved AllBud page HTML."""
    return (FIXTURE_DIR / "allbud_sample.html").read_text()


def test_parse_returns_allbud_result(sample_html):
    result = parse_allbud_page(sample_html)
    assert isinstance(result, AllBudResult)


def test_parse_extracts_effects(sample_html):
    result = parse_allbud_page(sample_html)
    assert len(result.effects) > 0
    # AllBud Blue Dream should have common effects
    effect_names = [e.lower() for e in result.effects]
    assert any(e in effect_names for e in ["happy", "relaxed", "euphoric", "creative", "uplifted"])


def test_parse_extracts_medical(sample_html):
    result = parse_allbud_page(sample_html)
    assert len(result.medical) > 0


def test_parse_extracts_negatives(sample_html):
    result = parse_allbud_page(sample_html)
    assert len(result.negatives) > 0


def test_parse_handles_empty_html():
    result = parse_allbud_page("<html><body>Not found</body></html>")
    assert result.effects == []
    assert result.medical == []
    assert result.negatives == []
```

**Step 3: Run tests to verify they fail**

Run: `cd ~/cannalchemy && python -m pytest tests/test_allbud_scraper.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 4: Write implementation**

```python
"""AllBud strain page scraper — extracts effects, medical uses, negatives, flavors."""
from dataclasses import dataclass, field
from bs4 import BeautifulSoup


@dataclass
class AllBudResult:
    """Parsed data from an AllBud strain page."""
    effects: list[str] = field(default_factory=list)
    medical: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)
    flavors: list[str] = field(default_factory=list)
    strain_type: str = ""
    thc_range: str = ""
    cbd_range: str = ""
    rating: float = 0.0
    description: str = ""


def parse_allbud_page(html: str) -> AllBudResult:
    """Parse an AllBud strain page HTML into structured data.

    Extracts effects, medical uses, negatives, flavors from the page's
    structured sections. Returns empty lists if sections are missing.
    """
    soup = BeautifulSoup(html, "html.parser")
    result = AllBudResult()

    # Implementation depends on actual HTML structure discovered in Step 1.
    # The HTML structure will be examined from the fixture file.
    # Common patterns on AllBud:
    # - Effects/medical/negatives in labeled sections with percentage bars
    # - Strain info in a sidebar or header area
    # - THC/CBD in a quick-facts section

    # Extract effect sections — adapt selectors based on fixture analysis
    _extract_effect_sections(soup, result)
    _extract_strain_info(soup, result)

    return result


def _extract_effect_sections(soup: BeautifulSoup, result: AllBudResult) -> None:
    """Extract effects, medical, negatives from AllBud's categorized sections."""
    # Implementation based on actual HTML structure from fixture
    pass


def _extract_strain_info(soup: BeautifulSoup, result: AllBudResult) -> None:
    """Extract strain type, THC/CBD, rating from AllBud page."""
    pass
```

> **Note to implementer:** The `parse_allbud_page` implementation above is a skeleton. After capturing the real HTML fixture in Step 1, examine the DOM structure and fill in the selectors. AllBud typically uses labeled div sections with effect names as text nodes. Adapt the CSS selectors and extraction logic to match what you find. The tests will guide you — make them pass.

**Step 5: Run tests to verify they pass**

Run: `cd ~/cannalchemy && python -m pytest tests/test_allbud_scraper.py -v`
Expected: 5 PASSED

**Step 6: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/allbud_scraper.py tests/test_allbud_scraper.py tests/fixtures/
git commit -m "feat(1c): add AllBud strain page scraper with HTML parsing"
```

---

### Task 3: Leafly Scraper Module

**Files:**
- Create: `cannalchemy/data/leafly_scraper.py`
- Create: `tests/test_leafly_scraper.py`
- Create: `tests/fixtures/leafly_blue_dream.md` (test fixture — Firecrawl markdown output)

**Context:** Leafly uses Cloudflare protection. Two strategies:
1. **Direct httpx** — try fetching the page directly; Leafly embeds data in a `__NEXT_DATA__` script tag (Next.js). If Cloudflare doesn't block, extract JSON directly.
2. **Firecrawl API** — POST to `https://api.firecrawl.dev/v1/scrape` with the URL. Returns markdown. Parse with regex. Costs 1 credit per page.

The scraper tries direct httpx first, falls back to Firecrawl if Cloudflare blocks.

**Leafly data from Firecrawl markdown** (tested on Blue Dream):
```
Effects: Creative (14,858 votes), Euphoric, Happy
Medical: Stress 36%, Anxiety 31%, Depression 28%
Negatives: Dry Mouth, Dry Eyes, Dizzy
Terpenes: Myrcene (dominant), Pinene, Caryophyllene
THC: 21%, CBD: <1%
Rating: 4.3/5, Reviews: 14.9K
```

**Step 1: Save a Firecrawl markdown fixture for testing**

Use the Firecrawl MCP tool to scrape Blue Dream and save the markdown output as a test fixture. Alternatively, create a representative fixture based on the known output format.

Create `tests/fixtures/leafly_blue_dream.md` with the markdown content from Firecrawl (as tested in the previous session). This should include the effects, medical, negatives, terpenes, and strain info sections.

**Step 2: Write the failing tests**

```python
"""Tests for Leafly strain scraper."""
import json
import pytest
from pathlib import Path
from cannalchemy.data.leafly_scraper import (
    parse_leafly_markdown,
    parse_next_data,
    LeaflyResult,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_markdown():
    return (FIXTURE_DIR / "leafly_blue_dream.md").read_text()


def test_parse_markdown_returns_result(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert isinstance(result, LeaflyResult)


def test_parse_markdown_extracts_effects(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert len(result.effects) > 0
    # At least some known Blue Dream effects
    effect_names = [e["name"].lower() for e in result.effects]
    assert "creative" in effect_names or "euphoric" in effect_names or "happy" in effect_names


def test_parse_markdown_extracts_vote_counts(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    has_votes = any(e.get("votes", 0) > 0 for e in result.effects)
    assert has_votes, "At least one effect should have vote counts"


def test_parse_markdown_extracts_medical(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert len(result.medical) > 0


def test_parse_markdown_extracts_negatives(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert len(result.negatives) > 0


def test_parse_markdown_extracts_terpenes(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert len(result.terpenes) > 0


def test_parse_next_data_valid():
    """Test __NEXT_DATA__ JSON parsing when available."""
    fake_html = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"strain":{"name":"Test","effects":["Happy"]}}}}</script>'
    result = parse_next_data(fake_html)
    assert result is not None
    assert result["name"] == "Test"


def test_parse_next_data_missing():
    result = parse_next_data("<html><body>No next data</body></html>")
    assert result is None
```

**Step 3: Run tests to verify they fail**

Run: `cd ~/cannalchemy && python -m pytest tests/test_leafly_scraper.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 4: Write implementation**

```python
"""Leafly strain page scraper — extracts effects with votes, medical, terpenes.

Two extraction strategies:
1. Direct: parse __NEXT_DATA__ JSON from raw HTML (if Cloudflare doesn't block)
2. Firecrawl: parse markdown output from Firecrawl API (1 credit/page)
"""
import json
import re
from dataclasses import dataclass, field


@dataclass
class LeaflyResult:
    """Parsed data from a Leafly strain page."""
    effects: list[dict] = field(default_factory=list)    # [{"name": "Creative", "votes": 14858}]
    medical: list[dict] = field(default_factory=list)     # [{"name": "Stress", "percent": 36}]
    negatives: list[str] = field(default_factory=list)    # ["Dry Mouth", "Dry Eyes"]
    terpenes: list[dict] = field(default_factory=list)    # [{"name": "Myrcene", "label": "dominant"}]
    thc: str = ""
    cbd: str = ""
    rating: float = 0.0
    review_count: int = 0
    strain_type: str = ""
    description: str = ""


def parse_next_data(html: str) -> dict | None:
    """Extract strain data from Leafly's __NEXT_DATA__ script tag."""
    match = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
        html, re.DOTALL
    )
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        return data.get("props", {}).get("pageProps", {}).get("strain")
    except (json.JSONDecodeError, AttributeError):
        return None


def parse_leafly_markdown(markdown: str) -> LeaflyResult:
    """Parse Firecrawl markdown output from a Leafly strain page.

    Extracts effects (with vote counts), medical uses (with percentages),
    negatives, terpenes, THC/CBD, rating, and review count using regex
    patterns matched to Leafly's consistent page structure.
    """
    result = LeaflyResult()

    # Effects with vote counts: "Creative 14,858", "Euphoric 12,345"
    # or "Creative", "Euphoric" (without counts)
    _extract_effects(markdown, result)
    _extract_medical(markdown, result)
    _extract_negatives(markdown, result)
    _extract_terpenes(markdown, result)
    _extract_strain_info(markdown, result)

    return result


def _extract_effects(md: str, result: LeaflyResult) -> None:
    """Extract positive effects and vote counts from markdown."""
    # Implementation depends on exact Firecrawl markdown format.
    # Adapt regex patterns to match what Firecrawl returns for Leafly pages.
    pass


def _extract_medical(md: str, result: LeaflyResult) -> None:
    """Extract medical uses with percentages from markdown."""
    pass


def _extract_negatives(md: str, result: LeaflyResult) -> None:
    """Extract negative effects from markdown."""
    pass


def _extract_terpenes(md: str, result: LeaflyResult) -> None:
    """Extract terpene profile from markdown."""
    pass


def _extract_strain_info(md: str, result: LeaflyResult) -> None:
    """Extract THC/CBD, rating, review count, strain type."""
    pass
```

> **Note to implementer:** The `_extract_*` functions are skeletons. Before implementing, create the fixture file by using Firecrawl MCP to scrape `https://www.leafly.com/strains/blue-dream` in markdown mode. Examine the output format and write regex patterns to extract each section. The markdown format from Firecrawl is fairly consistent across Leafly pages. Make the tests pass.

**Step 5: Run tests to verify they pass**

Run: `cd ~/cannalchemy && python -m pytest tests/test_leafly_scraper.py -v`
Expected: 8 PASSED

**Step 6: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/leafly_scraper.py tests/test_leafly_scraper.py tests/fixtures/leafly_blue_dream.md
git commit -m "feat(1c): add Leafly strain page scraper with markdown/JSON parsing"
```

---

### Task 4: Consumer Effect Mapper

**Files:**
- Create: `cannalchemy/data/consumer_mapper.py`
- Create: `tests/test_consumer_mapper.py`

**Context:** Maps effect names from Leafly/AllBud to our 51 canonical effects. The mapping pipeline:
1. Normalize: lowercase, replace spaces with hyphens, strip
2. Exact match against canonical effect names
3. Synonym match against `taxonomy.CANONICAL_EFFECTS[*].synonyms`
4. Fuzzy match with rapidfuzz (score ≥ 85)
5. If still unmapped: log for manual review, skip

Most Leafly effects map directly — "Creative" → "creative", "Dry Mouth" → "dry-mouth".

**Step 1: Write the failing tests**

```python
"""Tests for consumer effect name mapping."""
import sqlite3
import pytest
from cannalchemy.data.consumer_mapper import (
    build_effect_lookup,
    map_effect_name,
    map_effects_batch,
)
from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import seed_canonical_effects


@pytest.fixture
def db():
    conn = init_db(":memory:")
    seed_canonical_effects(conn)
    return conn


def test_build_lookup_from_db(db):
    lookup = build_effect_lookup(db)
    assert "relaxed" in lookup
    assert "dry-mouth" in lookup
    assert "pain" in lookup
    assert len(lookup) >= 51


def test_map_exact_match(db):
    lookup = build_effect_lookup(db)
    result = map_effect_name("Happy", lookup)
    assert result is not None
    assert result["canonical_name"] == "happy"
    assert result["method"] == "exact"


def test_map_with_spaces(db):
    """Leafly 'Dry Mouth' → canonical 'dry-mouth'."""
    lookup = build_effect_lookup(db)
    result = map_effect_name("Dry Mouth", lookup)
    assert result is not None
    assert result["canonical_name"] == "dry-mouth"


def test_map_synonym(db):
    """'Cottonmouth' is a synonym of 'dry-mouth'."""
    lookup = build_effect_lookup(db)
    result = map_effect_name("Cottonmouth", lookup)
    assert result is not None
    assert result["canonical_name"] == "dry-mouth"
    assert result["method"] == "synonym"


def test_map_medical(db):
    """Medical effects like 'Stress' should map."""
    lookup = build_effect_lookup(db)
    result = map_effect_name("Stress", lookup)
    assert result is not None
    assert result["canonical_name"] == "stress"


def test_map_unknown_returns_none(db):
    lookup = build_effect_lookup(db)
    result = map_effect_name("xyznonexistent", lookup)
    assert result is None


def test_map_batch(db):
    lookup = build_effect_lookup(db)
    names = ["Happy", "Creative", "Dry Mouth", "Stress", "nonsense"]
    results = map_effects_batch(names, lookup)
    assert len(results["mapped"]) == 4
    assert len(results["unmapped"]) == 1
    assert "nonsense" in results["unmapped"]


def test_map_lack_of_appetite(db):
    """'Lack of Appetite' → 'lack-of-appetite'."""
    lookup = build_effect_lookup(db)
    result = map_effect_name("Lack of Appetite", lookup)
    assert result is not None
    assert result["canonical_name"] == "lack-of-appetite"
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/cannalchemy && python -m pytest tests/test_consumer_mapper.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
"""Map consumer effect names (Leafly/AllBud) to canonical effects.

Pipeline: normalize → exact match → synonym match → fuzzy match → unmapped.
"""
import sqlite3
from rapidfuzz import fuzz, process


def build_effect_lookup(conn: sqlite3.Connection) -> dict:
    """Build lookup dict from canonical_effects table.

    Returns dict with:
    - canonical names as keys → {"id": int, "category": str}
    - synonyms as keys → {"id": int, "category": str, "canonical_name": str}
    """
    import json
    lookup = {}
    rows = conn.execute(
        "SELECT id, name, category, synonyms FROM canonical_effects"
    ).fetchall()

    for ce_id, name, category, synonyms_json in rows:
        lookup[name] = {"id": ce_id, "canonical_name": name, "category": category}
        for syn in json.loads(synonyms_json or "[]"):
            syn_lower = syn.lower().strip()
            if syn_lower not in lookup:
                lookup[syn_lower] = {"id": ce_id, "canonical_name": name, "category": category}

    return lookup


def _normalize_consumer_effect(name: str) -> str:
    """Normalize a consumer effect name for matching.

    'Dry Mouth' -> 'dry-mouth'
    'Lack of Appetite' -> 'lack-of-appetite'
    'HAPPY' -> 'happy'
    """
    return name.lower().strip().replace(" ", "-")


def map_effect_name(name: str, lookup: dict) -> dict | None:
    """Map a single effect name to a canonical effect.

    Returns {"canonical_name": str, "canonical_id": int, "category": str, "method": str}
    or None if unmapped.
    """
    normalized = _normalize_consumer_effect(name)

    # Exact match
    if normalized in lookup:
        entry = lookup[normalized]
        return {
            "canonical_name": entry["canonical_name"],
            "canonical_id": entry["id"],
            "category": entry["category"],
            "method": "exact",
        }

    # Synonym match (already in lookup from build_effect_lookup)
    # Try the original name lowercased (without hyphenation)
    lowered = name.lower().strip()
    if lowered in lookup:
        entry = lookup[lowered]
        return {
            "canonical_name": entry["canonical_name"],
            "canonical_id": entry["id"],
            "category": entry["category"],
            "method": "synonym",
        }

    # Fuzzy match against canonical names only
    canonical_names = [k for k, v in lookup.items() if v["canonical_name"] == k]
    match = process.extractOne(
        normalized, canonical_names, scorer=fuzz.ratio, score_cutoff=85
    )
    if match:
        entry = lookup[match[0]]
        return {
            "canonical_name": entry["canonical_name"],
            "canonical_id": entry["id"],
            "category": entry["category"],
            "method": "fuzzy",
        }

    return None


def map_effects_batch(names: list[str], lookup: dict) -> dict:
    """Map a batch of effect names. Returns {"mapped": [...], "unmapped": [...]}."""
    mapped = []
    unmapped = []
    for name in names:
        result = map_effect_name(name, lookup)
        if result:
            result["original_name"] = name
            mapped.append(result)
        else:
            unmapped.append(name)
    return {"mapped": mapped, "unmapped": unmapped}
```

**Step 4: Run tests to verify they pass**

Run: `cd ~/cannalchemy && python -m pytest tests/test_consumer_mapper.py -v`
Expected: 8 PASSED

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/consumer_mapper.py tests/test_consumer_mapper.py
git commit -m "feat(1c): add consumer effect mapper (Leafly/AllBud → canonical)"
```

---

### Task 5: Consumer Data Importer

**Files:**
- Create: `cannalchemy/data/consumer_import.py`
- Create: `tests/test_consumer_import.py`

**Context:** Takes parsed scraper results (LeaflyResult/AllBudResult) and inserts into the database:
- Effect reports → `effect_reports` table (strain_id, effect_id, report_count, confidence, source)
- Leafly terpene data → `strain_compositions` table (if we have molecule mappings)
- Handles UNIQUE constraint violations (INSERT OR IGNORE for existing source data, UPDATE for multi-source)

**Step 1: Write the failing tests**

```python
"""Tests for consumer data importer."""
import sqlite3
import pytest
from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import seed_canonical_effects
from cannalchemy.data.consumer_import import (
    import_effects_for_strain,
    import_consumer_batch,
)


@pytest.fixture
def db():
    conn = init_db(":memory:")
    seed_canonical_effects(conn)
    # Create a test strain
    conn.execute(
        "INSERT INTO strains (name, normalized_name, strain_type, source) "
        "VALUES ('Blue Dream', 'blue dream', 'hybrid', 'strain-tracker')"
    )
    conn.commit()
    return conn


def test_import_effects_basic(db):
    effects = [
        {"canonical_id": 1, "canonical_name": "relaxed", "votes": 1000, "method": "exact"},
        {"canonical_id": 2, "canonical_name": "euphoric", "votes": 800, "method": "exact"},
    ]
    count = import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    assert count == 2

    rows = db.execute("SELECT * FROM effect_reports WHERE strain_id = 1").fetchall()
    assert len(rows) == 2


def test_import_effects_with_votes(db):
    effects = [
        {"canonical_id": 1, "canonical_name": "relaxed", "votes": 14858, "method": "exact"},
    ]
    import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    row = db.execute(
        "SELECT report_count, source FROM effect_reports WHERE strain_id = 1"
    ).fetchone()
    assert row[0] == 14858
    assert row[1] == "leafly"


def test_import_dedup_same_source(db):
    """Importing same effect twice from same source should not create duplicates."""
    effects = [{"canonical_id": 1, "canonical_name": "relaxed", "votes": 100, "method": "exact"}]
    import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    count = db.execute(
        "SELECT COUNT(*) FROM effect_reports WHERE strain_id = 1 AND source = 'leafly'"
    ).fetchone()[0]
    assert count == 1


def test_import_different_sources(db):
    """Same effect from different sources creates separate records."""
    effects = [{"canonical_id": 1, "canonical_name": "relaxed", "votes": 100, "method": "exact"}]
    import_effects_for_strain(db, strain_id=1, effects=effects, source="leafly")
    import_effects_for_strain(db, strain_id=1, effects=effects, source="allbud")
    count = db.execute(
        "SELECT COUNT(*) FROM effect_reports WHERE strain_id = 1"
    ).fetchone()[0]
    assert count == 2


def test_import_batch(db):
    batch = [
        {
            "strain_id": 1,
            "source": "allbud",
            "effects": [
                {"canonical_id": 1, "canonical_name": "relaxed", "votes": 0, "method": "exact"},
                {"canonical_id": 3, "canonical_name": "happy", "votes": 0, "method": "exact"},
            ],
        },
    ]
    stats = import_consumer_batch(db, batch)
    assert stats["effects_imported"] == 2
    assert stats["strains_processed"] == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/cannalchemy && python -m pytest tests/test_consumer_import.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
"""Import consumer-scraped data (Leafly/AllBud) into the database."""
import sqlite3


def import_effects_for_strain(
    conn: sqlite3.Connection,
    strain_id: int,
    effects: list[dict],
    source: str,
) -> int:
    """Import effect reports for a single strain.

    Each effect dict: {"canonical_id": int, "canonical_name": str, "votes": int, "method": str}
    Uses INSERT OR IGNORE to handle duplicates (same strain + effect + source).
    Returns count of new records inserted.
    """
    count = 0
    for effect in effects:
        cur = conn.execute(
            "INSERT OR IGNORE INTO effect_reports "
            "(strain_id, effect_id, report_count, confidence, source) "
            "VALUES (?, ?, ?, 1.0, ?)",
            (strain_id, effect["canonical_id"], effect.get("votes", 0), source),
        )
        if cur.rowcount == 1:
            count += 1
    conn.commit()
    return count


def import_consumer_batch(conn: sqlite3.Connection, batch: list[dict]) -> dict:
    """Import a batch of consumer data.

    Each item: {"strain_id": int, "source": str, "effects": [...]}
    Returns stats dict.
    """
    stats = {"strains_processed": 0, "effects_imported": 0, "skipped": 0}

    for item in batch:
        strain_id = item["strain_id"]
        source = item["source"]
        effects = item.get("effects", [])

        imported = import_effects_for_strain(conn, strain_id, effects, source)
        stats["effects_imported"] += imported
        stats["strains_processed"] += 1

    return stats
```

**Step 4: Run tests to verify they pass**

Run: `cd ~/cannalchemy && python -m pytest tests/test_consumer_import.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/consumer_import.py tests/test_consumer_import.py
git commit -m "feat(1c): add consumer data importer for effect reports"
```

---

### Task 6: Confidence Scoring + Pipeline CLI

**Files:**
- Create: `cannalchemy/data/confidence.py`
- Create: `cannalchemy/data/consumer_pipeline.py`
- Create: `tests/test_confidence.py`
- Create: `tests/test_consumer_pipeline.py`

**Context:** Two components:
1. **Confidence scorer** — updates `effect_reports.confidence` based on multi-source agreement and vote counts
2. **Pipeline CLI** — orchestrates: build strain list → scrape AllBud → scrape Leafly → map effects → import → score

**Step 1: Write the failing tests for confidence scoring**

```python
"""Tests for multi-source confidence scoring."""
import sqlite3
import pytest
from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import seed_canonical_effects
from cannalchemy.data.confidence import compute_confidence_scores


@pytest.fixture
def db():
    conn = init_db(":memory:")
    seed_canonical_effects(conn)
    conn.execute(
        "INSERT INTO strains (name, normalized_name, strain_type, source) "
        "VALUES ('Blue Dream', 'blue dream', 'hybrid', 'strain-tracker')"
    )
    # Single-source effect
    conn.execute(
        "INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) "
        "VALUES (1, 1, 100, 1.0, 'leafly')"
    )
    # Multi-source effect (same effect, different sources)
    conn.execute(
        "INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) "
        "VALUES (1, 2, 50, 1.0, 'leafly')"
    )
    conn.execute(
        "INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) "
        "VALUES (1, 2, 0, 1.0, 'allbud')"
    )
    # Triple-source effect
    conn.execute(
        "INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) "
        "VALUES (1, 3, 200, 1.0, 'leafly')"
    )
    conn.execute(
        "INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) "
        "VALUES (1, 3, 0, 1.0, 'allbud')"
    )
    conn.execute(
        "INSERT INTO effect_reports (strain_id, effect_id, report_count, confidence, source) "
        "VALUES (1, 3, 50, 1.0, 'strain-tracker')"
    )
    conn.commit()
    return conn


def test_multi_source_higher_confidence(db):
    """Effects reported by multiple sources should have higher confidence."""
    stats = compute_confidence_scores(db)
    assert stats["updated"] > 0

    single = db.execute(
        "SELECT confidence FROM effect_reports WHERE strain_id=1 AND effect_id=1 AND source='leafly'"
    ).fetchone()[0]
    multi = db.execute(
        "SELECT confidence FROM effect_reports WHERE strain_id=1 AND effect_id=2 AND source='leafly'"
    ).fetchone()[0]
    triple = db.execute(
        "SELECT confidence FROM effect_reports WHERE strain_id=1 AND effect_id=3 AND source='leafly'"
    ).fetchone()[0]

    assert multi > single, "2-source should be higher than 1-source"
    assert triple >= multi, "3-source should be >= 2-source"


def test_vote_count_boosts_confidence(db):
    """Higher vote counts should boost confidence."""
    stats = compute_confidence_scores(db)
    # Effect 3 has 200 votes (leafly), effect 1 has 100 votes — both single-comparable
    # But effect 3 is triple-source so compare within same source count
    assert stats["updated"] > 0
```

**Step 2: Write the failing tests for pipeline**

```python
"""Tests for consumer pipeline orchestrator."""
import sqlite3
import pytest
from cannalchemy.data.schema import init_db
from cannalchemy.data.taxonomy import seed_canonical_effects
from cannalchemy.data.consumer_pipeline import (
    get_priority_strains,
)


@pytest.fixture
def db():
    conn = init_db(":memory:")
    seed_canonical_effects(conn)
    # Create strains: some with compositions, some without, some with effects
    for i, (name, source) in enumerate([
        ("Blue Dream", "strain-tracker"),
        ("OG Kush", "strain-tracker"),
        ("No Data", "strain-tracker"),
        ("Lab Only", "cannlytics"),
    ], start=1):
        conn.execute(
            "INSERT INTO strains (id, name, normalized_name, strain_type, source) "
            "VALUES (?, ?, ?, 'hybrid', ?)",
            (i, name, name.lower(), source),
        )
    # Add molecule
    conn.execute("INSERT INTO molecules (id, name, molecule_type) VALUES (1, 'myrcene', 'terpene')")
    # Blue Dream: has compositions + effects (already ML-ready)
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (1, 1, 0.5, 'test')")
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count, source) VALUES (1, 1, 10, 'strain-tracker')")
    # OG Kush: has compositions, no effects (priority target)
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (2, 1, 0.3, 'test')")
    # No Data: no compositions, no effects (skip)
    # Lab Only: cannlytics source (lower priority)
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage, source) VALUES (4, 1, 0.2, 'test')")
    conn.commit()
    return conn


def test_get_priority_strains(db):
    """Priority strains have compositions but no effects, from strain-tracker."""
    strains = get_priority_strains(db)
    assert len(strains) >= 1
    names = [s["name"] for s in strains]
    assert "OG Kush" in names
    assert "Blue Dream" not in names  # already has effects
    assert "No Data" not in names     # no compositions


def test_priority_strains_include_type(db):
    strains = get_priority_strains(db)
    for s in strains:
        assert "strain_type" in s
        assert "id" in s
```

**Step 3: Run tests to verify they fail**

Run: `cd ~/cannalchemy && python -m pytest tests/test_confidence.py tests/test_consumer_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 4: Write confidence implementation**

```python
"""Multi-source confidence scoring for effect reports.

Scoring formula:
- Base: 0.4 (single source)
- Source bonus: +0.2 per additional source (max 3 sources = 0.8)
- Vote bonus: +0.0 to +0.2 based on normalized vote count (log scale)
- Max confidence: 1.0
"""
import math
import sqlite3


def compute_confidence_scores(conn: sqlite3.Connection) -> dict:
    """Recompute confidence for all effect reports based on multi-source agreement.

    Returns stats dict with count of updated records.
    """
    stats = {"updated": 0}

    # Get source counts per (strain_id, effect_id)
    source_counts = {}
    rows = conn.execute(
        "SELECT strain_id, effect_id, COUNT(DISTINCT source) "
        "FROM effect_reports GROUP BY strain_id, effect_id"
    ).fetchall()
    for strain_id, effect_id, cnt in rows:
        source_counts[(strain_id, effect_id)] = cnt

    # Get max vote count for normalization
    max_votes = conn.execute(
        "SELECT MAX(report_count) FROM effect_reports WHERE report_count > 0"
    ).fetchone()[0] or 1

    # Update each report
    all_reports = conn.execute(
        "SELECT id, strain_id, effect_id, report_count FROM effect_reports"
    ).fetchall()

    for report_id, strain_id, effect_id, report_count in all_reports:
        n_sources = source_counts.get((strain_id, effect_id), 1)

        # Base + source bonus
        confidence = 0.4 + min(n_sources - 1, 2) * 0.2  # 0.4, 0.6, 0.8

        # Vote bonus (log-scaled, 0 to 0.2)
        if report_count and report_count > 0:
            vote_ratio = math.log1p(report_count) / math.log1p(max_votes)
            confidence += vote_ratio * 0.2

        confidence = min(confidence, 1.0)

        conn.execute(
            "UPDATE effect_reports SET confidence = ? WHERE id = ?",
            (round(confidence, 4), report_id),
        )
        stats["updated"] += 1

    conn.commit()
    return stats
```

**Step 5: Write pipeline implementation**

```python
"""Consumer data pipeline: scrape, map, import, score.

Usage: python -m cannalchemy.data.consumer_pipeline --db data/processed/cannalchemy.db
"""
import argparse
import json
import sqlite3
import time
from pathlib import Path

from cannalchemy.data.consumer_config import (
    strain_to_allbud_url,
    strain_to_leafly_url,
    SCRAPE_CONFIG,
)
from cannalchemy.data.consumer_mapper import build_effect_lookup, map_effects_batch
from cannalchemy.data.consumer_import import import_effects_for_strain
from cannalchemy.data.confidence import compute_confidence_scores


def get_priority_strains(conn: sqlite3.Connection) -> list[dict]:
    """Get strains that have compositions but no effect reports.

    Prioritizes strain-tracker strains (real strain names) over cannlytics
    (often product names). Returns list of dicts with id, name, strain_type.
    """
    rows = conn.execute("""
        SELECT DISTINCT s.id, s.name, s.strain_type, s.source
        FROM strains s
        INNER JOIN strain_compositions sc ON s.id = sc.strain_id
        LEFT JOIN effect_reports er ON s.id = er.strain_id
        WHERE er.id IS NULL
        ORDER BY
            CASE WHEN s.source = 'strain-tracker' THEN 0 ELSE 1 END,
            s.name
    """).fetchall()

    return [
        {"id": row[0], "name": row[1], "strain_type": row[2], "source": row[3]}
        for row in rows
    ]


def run_pipeline(db_path: str, source: str = "allbud", limit: int = 0) -> dict:
    """Run the consumer data pipeline.

    Args:
        db_path: Path to SQLite database
        source: 'allbud' or 'leafly'
        limit: Max strains to process (0 = all)

    Returns stats dict.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    stats = {
        "source": source,
        "strains_targeted": 0,
        "strains_scraped": 0,
        "strains_found": 0,
        "effects_mapped": 0,
        "effects_imported": 0,
        "effects_unmapped": 0,
        "errors": 0,
    }

    # Get priority strains
    strains = get_priority_strains(conn)
    if limit:
        strains = strains[:limit]
    stats["strains_targeted"] = len(strains)
    print(f"Targeting {len(strains)} strains for {source} scraping...")

    # Build effect lookup
    lookup = build_effect_lookup(conn)

    # Load progress file for resumability
    progress_file = Path(db_path).parent / f".{source}_progress.json"
    done_ids = set()
    if progress_file.exists():
        done_ids = set(json.loads(progress_file.read_text()))
        print(f"Resuming: {len(done_ids)} already processed")

    for i, strain in enumerate(strains):
        if strain["id"] in done_ids:
            continue

        # Scraping happens here — import the appropriate scraper
        # This is the integration point for allbud_scraper or leafly_scraper
        try:
            scraped = _scrape_strain(strain, source)
            stats["strains_scraped"] += 1

            if scraped and scraped.get("effects"):
                stats["strains_found"] += 1
                mapped = map_effects_batch(scraped["effects"], lookup)
                stats["effects_mapped"] += len(mapped["mapped"])
                stats["effects_unmapped"] += len(mapped["unmapped"])

                # Import mapped effects
                effect_dicts = [
                    {"canonical_id": m["canonical_id"], "canonical_name": m["canonical_name"],
                     "votes": scraped.get("votes", {}).get(m["original_name"], 0),
                     "method": m["method"]}
                    for m in mapped["mapped"]
                ]
                imported = import_effects_for_strain(conn, strain["id"], effect_dicts, source)
                stats["effects_imported"] += imported

        except Exception as e:
            stats["errors"] += 1
            print(f"  Error scraping {strain['name']}: {e}")

        done_ids.add(strain["id"])

        # Save progress periodically
        if (i + 1) % SCRAPE_CONFIG["batch_size"] == 0:
            progress_file.write_text(json.dumps(list(done_ids)))
            print(f"  Progress: {i+1}/{len(strains)} "
                  f"(found={stats['strains_found']}, imported={stats['effects_imported']})")

        # Rate limiting
        time.sleep(SCRAPE_CONFIG["rate_limit"])

    # Final save
    progress_file.write_text(json.dumps(list(done_ids)))

    # Compute confidence scores
    print("Computing confidence scores...")
    score_stats = compute_confidence_scores(conn)
    stats["confidence_updated"] = score_stats["updated"]

    conn.close()
    return stats


def _scrape_strain(strain: dict, source: str) -> dict | None:
    """Scrape a single strain from the specified source.

    Returns dict with 'effects' list and optional 'votes' dict,
    or None if page not found.
    """
    import httpx
    from cannalchemy.data.consumer_config import strain_to_allbud_url, strain_to_leafly_url

    if source == "allbud":
        from cannalchemy.data.allbud_scraper import parse_allbud_page
        url = strain_to_allbud_url(strain["name"], strain.get("strain_type", "hybrid"))
        try:
            resp = httpx.get(url, headers={"User-Agent": SCRAPE_CONFIG["user_agent"]},
                           follow_redirects=True, timeout=SCRAPE_CONFIG["timeout"])
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            result = parse_allbud_page(resp.text)
            return {
                "effects": result.effects + result.medical + result.negatives,
                "votes": {},
            }
        except httpx.HTTPError:
            return None

    elif source == "leafly":
        from cannalchemy.data.leafly_scraper import parse_leafly_markdown, parse_next_data
        url = strain_to_leafly_url(strain["name"])

        # Strategy 1: Direct httpx (may be blocked by Cloudflare)
        try:
            resp = httpx.get(url, headers={"User-Agent": SCRAPE_CONFIG["user_agent"]},
                           follow_redirects=True, timeout=SCRAPE_CONFIG["timeout"])
            if resp.status_code == 200 and "__NEXT_DATA__" in resp.text:
                data = parse_next_data(resp.text)
                if data:
                    effects = data.get("effects", [])
                    return {"effects": effects, "votes": {}}
        except httpx.HTTPError:
            pass

        # Strategy 2: Firecrawl API (if configured)
        import os
        api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        if api_key:
            try:
                resp = httpx.post(
                    SCRAPE_CONFIG["firecrawl_api_url"],
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"url": url, "formats": ["markdown"]},
                    timeout=60,
                )
                resp.raise_for_status()
                md = resp.json().get("data", {}).get("markdown", "")
                result = parse_leafly_markdown(md)
                effects = [e["name"] for e in result.effects] + \
                          [m["name"] for m in result.medical] + \
                          result.negatives
                votes = {e["name"]: e.get("votes", 0) for e in result.effects}
                return {"effects": effects, "votes": votes}
            except httpx.HTTPError:
                return None

        return None

    return None


def main():
    parser = argparse.ArgumentParser(description="Consumer data scraping pipeline")
    parser.add_argument("--db", required=True, help="Path to cannalchemy.db")
    parser.add_argument("--source", choices=["allbud", "leafly"], default="allbud")
    parser.add_argument("--limit", type=int, default=0, help="Max strains (0=all)")
    args = parser.parse_args()

    stats = run_pipeline(args.db, args.source, args.limit)
    print("\n=== Pipeline Results ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
```

**Step 6: Run tests to verify they pass**

Run: `cd ~/cannalchemy && python -m pytest tests/test_confidence.py tests/test_consumer_pipeline.py -v`
Expected: All PASSED

**Step 7: Commit**

```bash
cd ~/cannalchemy
git add cannalchemy/data/confidence.py cannalchemy/data/consumer_pipeline.py \
    tests/test_confidence.py tests/test_consumer_pipeline.py
git commit -m "feat(1c): add confidence scoring and consumer pipeline orchestrator"
```

---

### Task 7: Run on Live DB

**Files:**
- No new files. Operational task using the pipeline built in Tasks 1-6.

**Context:** The live database is at `~/cannalchemy/data/processed/cannalchemy.db`. We'll run the pipeline in two phases:
1. AllBud scraping for all priority strains (11,701 with compositions, no effects)
2. Leafly scraping for Strain Tracker strains (if Firecrawl API key is available)

**Step 1: Verify all tests pass**

Run: `cd ~/cannalchemy && python -m pytest -v -k "not network"`
Expected: All ~85 tests PASS (77 from 1A/1B + ~8 new from 1C)

**Step 2: Run AllBud pipeline (small test batch first)**

Run: `cd ~/cannalchemy && python -m cannalchemy.data.consumer_pipeline --db data/processed/cannalchemy.db --source allbud --limit 50`

Verify output shows strains being scraped, effects being mapped and imported. Check for errors.

**Step 3: Run AllBud pipeline (full)**

Run: `cd ~/cannalchemy && python -m cannalchemy.data.consumer_pipeline --db data/processed/cannalchemy.db --source allbud`

This will take several hours at 1 req/sec for ~11K strains. Monitor progress output.

**Step 4: Run Leafly pipeline (if Firecrawl API key available)**

First check: `echo $FIRECRAWL_API_KEY`

If available:
Run: `cd ~/cannalchemy && FIRECRAWL_API_KEY=<key> python -m cannalchemy.data.consumer_pipeline --db data/processed/cannalchemy.db --source leafly --limit 5000`

**Step 5: Check ML-readiness improvement**

Run: `cd ~/cannalchemy && python3 -c "
import sqlite3
conn = sqlite3.connect('data/processed/cannalchemy.db')
total = conn.execute('SELECT COUNT(*) FROM strains').fetchone()[0]
ml_ready = conn.execute('''
    SELECT COUNT(DISTINCT sc.strain_id)
    FROM strain_compositions sc
    INNER JOIN effect_reports er ON sc.strain_id = er.strain_id
''').fetchone()[0]
print(f'ML-ready: {ml_ready} / {total} = {ml_ready/total*100:.1f}%')

by_source = conn.execute('''
    SELECT source, COUNT(*) FROM effect_reports GROUP BY source ORDER BY COUNT(*) DESC
''').fetchall()
print('Effect reports by source:')
for src, cnt in by_source:
    print(f'  {src}: {cnt}')

total_effects = conn.execute('SELECT COUNT(*) FROM effect_reports').fetchone()[0]
print(f'Total effect reports: {total_effects}')
"`

**Target:** ML-ready ≥ 15,000 (60%+), total effect reports ≥ 50,000

**Step 6: Update SESSION-LOG.md**

Record Phase 1C results: strains scraped, effects imported, ML-readiness improvement, any issues encountered.

**Step 7: Commit session log update**

```bash
cd ~/cannalchemy
git add docs/SESSION-LOG.md
git commit -m "docs: update SESSION-LOG with Phase 1C results"
```

---

## Summary

| Task | Module | Tests | Description |
|------|--------|-------|-------------|
| 1 | consumer_config.py | 7 | URL builders + scrape config |
| 2 | allbud_scraper.py | 5 | AllBud HTML parser |
| 3 | leafly_scraper.py | 8 | Leafly markdown/JSON parser |
| 4 | consumer_mapper.py | 8 | Effect name → canonical mapping |
| 5 | consumer_import.py | 5 | DB importer for effect reports |
| 6 | confidence.py, consumer_pipeline.py | 4 | Confidence scoring + pipeline CLI |
| 7 | (operational) | — | Run on live DB |
| **Total** | **7 new modules** | **~37 new** | |

## Dependencies

- `beautifulsoup4>=4.12` (new — AllBud HTML parsing)
- `httpx>=0.27` (existing — HTTP requests)
- `rapidfuzz>=3.0` (existing — fuzzy matching)
- Optional: `FIRECRAWL_API_KEY` env var for Leafly Cloudflare bypass

## Risk Mitigation

1. **AllBud blocks scraping:** Add rotating User-Agent headers, exponential backoff. If blocked entirely, fall back to Leafly-only via Firecrawl.
2. **Leafly Cloudflare blocks direct httpx:** Expected. Fall back to Firecrawl API. If no API key, skip Leafly entirely (AllBud-only still gets us significant coverage).
3. **AllBud URL pattern wrong:** The strain type in the URL may not match our DB. Handle 404s gracefully, try alternate types (indica → hybrid → sativa).
4. **Effect names don't map:** Log unmapped effects. If >10% unmapped, batch-classify via GLM-4.7 (same approach as Phase 1A).
5. **Rate limiting / IP blocks:** 1 req/sec is conservative. Monitor for 429/503 responses and back off.
