"""Download Cannlytics data files from HuggingFace."""
import os
from huggingface_hub import hf_hub_download
from cannalchemy.data.cannlytics_config import STATE_CONFIGS

REPO_ID = "cannlytics/cannabis_results"
DEFAULT_CACHE_DIR = "data/raw/cannlytics"


def get_cache_path(state: str, cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """Get expected local path for a state's data file."""
    cfg = STATE_CONFIGS[state]
    ext = "xlsx" if cfg["file_type"] == "xlsx" else "csv"
    return os.path.join(cache_dir, f"{state}-results-latest.{ext}")


def download_state(state: str, cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    """Download a state's data file from HuggingFace. Returns path."""
    cfg = STATE_CONFIGS[state]
    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=cfg["file"],
        repo_type="dataset",
        cache_dir=os.path.join(cache_dir, "hf_cache"),
    )
    return path


def download_all_states(cache_dir: str = DEFAULT_CACHE_DIR) -> dict[str, str]:
    """Download all configured states. Returns {state: path} dict."""
    results = {}
    for state in STATE_CONFIGS:
        try:
            path = download_state(state, cache_dir)
            results[state] = path
            print(f"  Downloaded {state.upper()}: {path}")
        except Exception as e:
            print(f"  FAILED {state.upper()}: {e}")
    return results
