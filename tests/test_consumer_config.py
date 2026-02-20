"""Tests for consumer scraping configuration and URL builders."""
from cannalchemy.data.consumer_config import (
    SCRAPE_CONFIG,
    strain_to_leafly_url,
    strain_to_allbud_url,
)


def test_leafly_url_basic():
    assert strain_to_leafly_url("Blue Dream") == "https://www.leafly.com/strains/blue-dream"


def test_leafly_url_og_kush():
    assert strain_to_leafly_url("O.G. Kush") == "https://www.leafly.com/strains/og-kush"


def test_leafly_url_special_chars():
    assert strain_to_leafly_url("Girl Scout Cookies #4") == "https://www.leafly.com/strains/girl-scout-cookies-4"


def test_allbud_url_basic():
    url = strain_to_allbud_url("Blue Dream", "sativa")
    assert url == "https://www.allbud.com/marijuana-strains/sativa/blue-dream"


def test_allbud_url_unknown_type():
    url = strain_to_allbud_url("Mystery Strain", "unknown")
    assert url == "https://www.allbud.com/marijuana-strains/hybrid/mystery-strain"


def test_allbud_url_indica():
    url = strain_to_allbud_url("Northern Lights", "indica")
    assert url == "https://www.allbud.com/marijuana-strains/indica/northern-lights"


def test_scrape_config_defaults():
    assert SCRAPE_CONFIG["rate_limit"] > 0
    assert SCRAPE_CONFIG["max_retries"] >= 1
    assert "firecrawl_api_url" in SCRAPE_CONFIG
