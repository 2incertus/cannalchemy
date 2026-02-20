"""AllBud strain page HTML scraper.

Parses strain detail pages from allbud.com to extract effects,
medical uses, flavors, cannabinoid percentages, and other metadata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup


@dataclass
class AllBudResult:
    """Parsed data from an AllBud strain detail page."""

    effects: list[str] = field(default_factory=list)
    medical: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)
    flavors: list[str] = field(default_factory=list)
    strain_type: str = ""
    thc_range: str = ""
    cbd_range: str = ""
    rating: float = 0.0
    description: str = ""


# Map panel heading text (lowered, stripped) to AllBudResult field name.
_HEADING_MAP: dict[str, str] = {
    "effects": "effects",
    "may relieve": "medical",
    "flavors": "flavors",
    "negatives": "negatives",
    "side effects": "negatives",
}


def _extract_tags(card_div) -> list[str]:
    """Extract tag names from a flip-card's tags-list section."""
    tags_div = card_div.find("div", class_="tags-list")
    if not tags_div:
        return []
    return [a.get_text(strip=True) for a in tags_div.find_all("a") if a.get_text(strip=True)]


def _clean_heading(text: str) -> str:
    """Normalize a panel heading to a lookup key."""
    # Strip whitespace and remove any trailing icon / tooltip text
    cleaned = text.strip()
    # Remove trailing disclaimer icon text that may leak through
    # e.g. "May Relieve Disclaimer: ..."
    for sep in ["Disclaimer", "\n"]:
        if sep in cleaned:
            cleaned = cleaned[: cleaned.index(sep)]
    return cleaned.strip().lower()


def _extract_thc_cbd(soup: BeautifulSoup) -> tuple[str, str]:
    """Extract THC and CBD ranges from the percentage h4 element."""
    thc_range = ""
    cbd_range = ""

    h4 = soup.find("h4", class_="percentage")
    if not h4:
        return thc_range, cbd_range

    text = h4.get_text(" ", strip=True)

    # THC pattern: "THC: 17% - 24%" or "THC: 22%"
    thc_match = re.search(r"THC:\s*([\d]+%?\s*-?\s*[\d]*%?)", text)
    if thc_match:
        thc_range = thc_match.group(1).strip().rstrip(",")

    # CBD pattern: "CBD: 2%" or "CBD: 0.1% - 1%"
    cbd_match = re.search(r"CBD:\s*([\d.]+%?\s*-?\s*[\d.]*%?)", text)
    if cbd_match:
        cbd_range = cbd_match.group(1).strip().rstrip(",")

    return thc_range, cbd_range


def _extract_strain_type(soup: BeautifulSoup) -> str:
    """Extract strain type (e.g. 'Sativa Dominant Hybrid') from the variety h4."""
    h4 = soup.find("h4", class_="variety")
    if not h4:
        return ""
    link = h4.find("a")
    if link:
        return link.get_text(strip=True)
    return ""


def _extract_rating(soup: BeautifulSoup) -> float:
    """Extract numeric rating from span.rating-num."""
    span = soup.find("span", class_="rating-num")
    if not span:
        return 0.0
    try:
        return float(span.get_text(strip=True))
    except (ValueError, TypeError):
        return 0.0


def _extract_description(soup: BeautifulSoup) -> str:
    """Extract the strain description text from the description panel."""
    desc_div = soup.find("div", class_="description")
    if not desc_div:
        return ""
    # The description is in a <span> directly inside the description div,
    # after the variety/percentage h4 elements.
    for span in desc_div.find_all("span", recursive=False):
        text = span.get_text(" ", strip=True)
        # Skip short utility spans; the real description is long prose
        if len(text) > 50:
            return text
    return ""


def parse_allbud_page(html: str) -> AllBudResult:
    """Parse an AllBud strain detail page and return structured data.

    Args:
        html: Raw HTML string of the strain page.

    Returns:
        AllBudResult with extracted fields. Missing sections yield empty
        lists / strings / 0.0 rather than raising.
    """
    soup = BeautifulSoup(html, "html.parser")
    result = AllBudResult()

    # --- Flip-card panels (Effects, May Relieve, Flavors, Aromas, Negatives) ---
    # Use only the desktop "face front" cards (hidden-xs class panels are
    # the mobile duplicates; we skip those by targeting section IDs within
    # the hidden-xs column, but easier: just grab the first match per heading).
    seen_headings: set[str] = set()

    for card in soup.find_all("div", class_="face"):
        if "front" not in card.get("class", []):
            continue
        heading_div = card.find("div", class_="panel-heading")
        if not heading_div:
            continue

        heading_key = _clean_heading(heading_div.get_text())
        if heading_key in seen_headings:
            continue  # skip mobile duplicate
        seen_headings.add(heading_key)

        field_name = _HEADING_MAP.get(heading_key)
        if field_name is None:
            continue  # e.g. "Strain Information", "Aromas" — skip

        tags = _extract_tags(card)
        setattr(result, field_name, tags)

    # --- THC / CBD ---
    result.thc_range, result.cbd_range = _extract_thc_cbd(soup)

    # --- Strain type ---
    result.strain_type = _extract_strain_type(soup)

    # --- Rating ---
    result.rating = _extract_rating(soup)

    # --- Description ---
    result.description = _extract_description(soup)

    return result
