import os
import json
import pytest
from src.cache_utils import is_empty_data, mark_empty_data, CACHE_FILE

@pytest.fixture(autouse=True)
def clean_cache():
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    yield
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)

def test_cache_operations():
    assert is_empty_data("test_key") is False
    mark_empty_data("test_key")
    assert is_empty_data("test_key") is True
