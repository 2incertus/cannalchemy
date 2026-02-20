"""Consumer site scraping configuration and URL builders for Leafly/AllBud."""
import os
import re


def _load_firecrawl_key() -> str:
    """Load Firecrawl API key from env var or Strain Tracker .env file."""
    key = os.environ.get("FIRECRAWL_API_KEY", "")
    if key:
        return key
    st_env = "/home/ubuntu/docker/strain-tracker/.env"
    try:
        with open(st_env) as f:
            for line in f:
                line = line.strip()
                if line.startswith("FIRECRAWL_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    except FileNotFoundError:
        pass
    return ""


SCRAPE_CONFIG = {
    "rate_limit": 1.0,
    "max_retries": 3,
    "retry_delay": 5.0,
    "timeout": 30.0,
    "firecrawl_api_url": "https://api.firecrawl.dev/v1",
    "firecrawl_api_key": _load_firecrawl_key(),
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "batch_size": 100,
}

_VALID_TYPE_MAP = {"sativa", "indica", "hybrid"}


def _slugify(name: str) -> str:
    """Convert a strain name to a URL slug.

    Lowercase, remove periods, strip special characters (keep alphanumeric,
    spaces, hyphens), replace spaces with hyphens, collapse multiple hyphens.
    """
    slug = name.lower()
    slug = slug.replace(".", "")
    slug = re.sub(r"[^a-z0-9 \-]", "", slug)
    slug = slug.replace(" ", "-")
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    return slug


def strain_to_leafly_url(name: str) -> str:
    """Build a Leafly strain URL from a strain name."""
    return f"https://www.leafly.com/strains/{_slugify(name)}"


def strain_to_allbud_url(name: str, strain_type: str) -> str:
    """Build an AllBud strain URL from a strain name and type.

    If strain_type is not one of sativa/indica/hybrid, defaults to hybrid.
    """
    st = strain_type.lower() if strain_type else "hybrid"
    if st not in _VALID_TYPE_MAP:
        st = "hybrid"
    return f"https://www.allbud.com/marijuana-strains/{st}/{_slugify(name)}"
