"""Tests for Cannlytics HuggingFace download pipeline."""
import os
from unittest.mock import patch, MagicMock
from cannalchemy.data.cannlytics_download import download_state, get_cache_path
from cannalchemy.data.cannlytics_config import STATE_CONFIGS

def test_get_cache_path():
    path = get_cache_path("nv")
    assert "nv" in path
    assert path.endswith(".csv") or path.endswith(".xlsx")

def test_get_cache_path_invalid_state():
    import pytest
    with pytest.raises(KeyError):
        get_cache_path("xx")

def test_download_uses_hf_hub(tmp_path):
    """Test download calls huggingface_hub correctly."""
    with patch("cannalchemy.data.cannlytics_download.hf_hub_download") as mock_dl:
        mock_dl.return_value = str(tmp_path / "test.csv")
        (tmp_path / "test.csv").write_text("a,b\n1,2\n")
        result = download_state("nv", cache_dir=str(tmp_path))
        mock_dl.assert_called_once()
        assert result == str(tmp_path / "test.csv")
