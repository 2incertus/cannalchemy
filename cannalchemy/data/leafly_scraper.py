"""Leafly strain page scraper — parse Firecrawl markdown and __NEXT_DATA__ JSON."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class LeaflyResult:
    """Structured data extracted from a Leafly strain page."""

    effects: list[dict] = field(default_factory=list)  # [{"name": "Creative", "votes": 14858}]
    medical: list[dict] = field(default_factory=list)  # [{"name": "Stress", "percent": 36}]
    negatives: list[str] = field(default_factory=list)  # ["Dry mouth", "Dry eyes", "Dizzy"]
    terpenes: list[str] = field(default_factory=list)  # ["Myrcene", "Pinene", "Caryophyllene"]
    flavors: list[str] = field(default_factory=list)  # ["Berry", "Blueberry", "Sweet"]
    thc: str = ""  # "21%"
    cbd: str = ""  # "0%"
    rating: float = 0.0  # 4.3
    review_count: int = 0  # 14858
    strain_type: str = ""  # "Hybrid"
    description: str = ""


def parse_leafly_markdown(markdown: str) -> LeaflyResult:
    """Parse Firecrawl markdown output from a Leafly strain page.

    Extracts effects, medical uses, negatives, terpenes, flavors,
    THC/CBD percentages, rating, review count, strain type, and description.
    """
    result = LeaflyResult()

    # --- Strain type ---
    # Pattern: [Hybrid](https://...) or [Sativa](https://...) etc in header area
    strain_type_match = re.search(
        r"^\[(\w+)\]\(https://www\.leafly\.com/strains/lists/category/",
        markdown,
        re.MULTILINE,
    )
    if strain_type_match:
        result.strain_type = strain_type_match.group(1)

    # --- THC / CBD ---
    # Pattern: THC21%CBD0% (may appear on the same line as strain type link)
    thc_cbd_match = re.search(r"THC(\d+%)(?:CBD(\d+%))?", markdown)
    if thc_cbd_match:
        result.thc = thc_cbd_match.group(1)
        if thc_cbd_match.group(2):
            result.cbd = thc_cbd_match.group(2)

    # --- Rating ---
    # Pattern: [4.3(14.9k ratings)](https://...)
    rating_match = re.search(r"\[(\d+\.?\d*)\([\d.]+k? ratings\)\]", markdown)
    if rating_match:
        result.rating = float(rating_match.group(1))

    # --- Review count / vote count from "Reported by N real people" ---
    reported_match = re.search(r"Reported by (\d+) real people", markdown)
    vote_count = 0
    if reported_match:
        vote_count = int(reported_match.group(1))
        result.review_count = vote_count

    # --- Description ---
    # Bold strain name followed by description text: **Blue Dream** is a ...
    desc_match = re.search(r"\*\*[^*]+\*\*\s+(.+?)(?:\n\n|\Z)", markdown, re.DOTALL)
    if desc_match:
        # Include the bold name as part of the description
        full_desc_match = re.search(
            r"(\*\*[^*]+\*\*\s+.+?)(?:\n\n|\Z)", markdown, re.DOTALL
        )
        if full_desc_match:
            result.description = full_desc_match.group(1).strip()

    # --- Positive Effects ---
    # Section: ### Positive Effects followed by [EffectName](url) links
    pos_section = re.search(
        r"### Positive Effects\s*\n(.*?)(?=###|\Z)", markdown, re.DOTALL
    )
    if pos_section:
        effect_links = re.findall(r"\[([^\]]+)\]\(https://", pos_section.group(1))
        result.effects = [{"name": name, "votes": vote_count} for name in effect_links]

    # --- Negative Effects ---
    neg_section = re.search(
        r"### Negative Effects\s*\n(.*?)(?=##|\Z)", markdown, re.DOTALL
    )
    if neg_section:
        neg_links = re.findall(r"\[([^\]]+)\]\(https://", neg_section.group(1))
        result.negatives = neg_links

    # --- Terpenes ---
    # Pattern: [Terpenes](url) followed by bare words, one per line, separated by blank lines
    terpene_section = re.search(
        r"\[Terpenes\]\([^\)]+\)\s*\n(.*?)(?=\n\[|\n[a-z]|\Z)",
        markdown,
        re.DOTALL,
    )
    if terpene_section:
        lines = terpene_section.group(1).strip().split("\n")
        result.terpenes = [
            line.strip()
            for line in lines
            if line.strip() and re.match(r"^[A-Z][a-z]+$", line.strip())
        ]

    # --- Flavors ---
    # Strategy 1: [Top flavors](url) followed by bare words, one per line
    flavor_section = re.search(
        r"\[Top flavors\]\([^\)]+\)\s*\n(.*?)(?=\n\[|\Z)",
        markdown,
        re.DOTALL,
    )
    if flavor_section:
        lines = flavor_section.group(1).strip().split("\n")
        result.flavors = [
            line.strip()
            for line in lines
            if line.strip() and re.match(r"^[A-Z][a-z]+$", line.strip())
        ]

    # Strategy 2: ## ... strain flavors section with links
    if not result.flavors:
        flavor_heading = re.search(
            r"## .+ strain flavors\s*\n(.*?)(?=##|\Z)", markdown, re.DOTALL
        )
        if flavor_heading:
            flavor_links = re.findall(
                r"\[([^\]]+)\]\(https://www\.leafly\.com/strains/lists/flavor/",
                flavor_heading.group(1),
            )
            result.flavors = flavor_links

    # --- Medical ---
    # Pattern: ## ... strain helps with
    # - [Stress](url)
    # 36% of people say it helps with Stress
    medical_section = re.search(
        r"## .+ strain helps with\s*\n(.*?)(?=##|\Z)", markdown, re.DOTALL
    )
    if medical_section:
        # Find pairs: name from link + percent from text
        medical_entries = re.findall(
            r"-\s*\[([^\]]+)\]\([^\)]+\)\s*\n\s*\n?\s*(\d+)% of people say it helps with",
            medical_section.group(1),
        )
        result.medical = [
            {"name": name, "percent": int(pct)} for name, pct in medical_entries
        ]

    return result


def parse_next_data(html: str) -> dict | None:
    """Extract strain data from Leafly's __NEXT_DATA__ script tag.

    For direct httpx scraping strategy: parse the embedded JSON to get
    the strain data object.

    Returns the strain dict, or None if not found.
    """
    match = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">\s*({.*?})\s*</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        strain = data.get("props", {}).get("pageProps", {}).get("strain")
        return strain
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
