import os
import pytest
import src.cache_utils as cache_utils
from src.cache_utils import is_empty_data, mark_empty_data

@pytest.fixture(autouse=True)
def setup_cache(tmp_path, monkeypatch):
    cache_file = tmp_path / "empty_records.json"
    monkeypatch.setattr(cache_utils, "CACHE_FILE", str(cache_file))

def test_cache_operations():
    assert is_empty_data("test_key") is False
    mark_empty_data("test_key")
    assert is_empty_data("test_key") is True
