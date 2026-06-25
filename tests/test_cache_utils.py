import pytest
import os
import json
from unittest.mock import patch, mock_open
from src.utils.cache_utils import _load_cache, _save_cache, is_empty_data, mark_empty_data, save_league_metadata, load_league_metadata

@pytest.fixture
def mock_cache_file(tmp_path):
    # Setup a temporary file path for tests
    return str(tmp_path / "test_cache.json")

def test_load_cache_not_exists(mock_cache_file):
    assert _load_cache(mock_cache_file) == {}

@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data='{"key1": true}')
def test_load_cache_exists_valid(mock_file, mock_exists):
    assert _load_cache("dummy_path") == {"key1": True}

@patch("os.path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data='invalid json')
def test_load_cache_exists_invalid(mock_file, mock_exists):
    assert _load_cache("dummy_path") == {}

@patch("os.makedirs")
@patch("os.replace")
def test_save_cache(mock_replace, mock_makedirs):
    data = {"test": 123}
    m = mock_open()
    with patch("builtins.open", m):
        _save_cache(data, "dummy_path")
        
    mock_makedirs.assert_called_once_with(os.path.dirname("dummy_path"), exist_ok=True)
    m.assert_called_once_with("dummy_path.tmp", "w", encoding="utf-8")
    # Verify write was called (mock_open write can be tricky to assert exact string, 
    # but we can verify it was called)
    assert m().write.called
    mock_replace.assert_called_once_with("dummy_path.tmp", "dummy_path")

@patch("src.utils.cache_utils._load_cache", return_value={"test_key": True})
def test_is_empty_data_true(mock_load):
    assert is_empty_data("test_key") is True

@patch("src.utils.cache_utils._load_cache", return_value={})
def test_is_empty_data_false(mock_load):
    assert is_empty_data("test_key") is False

@patch("src.utils.cache_utils._load_cache", return_value={})
@patch("src.utils.cache_utils._save_cache")
@patch("src.utils.cache_utils.FileLock")
def test_mark_empty_data(mock_lock, mock_save, mock_load):
    mark_empty_data("new_key")
    # verify save was called with the updated dict
    mock_save.assert_called_once()
    assert mock_save.call_args[0][0] == {"new_key": True}

@patch("src.utils.cache_utils._load_cache", return_value={"league_id": "123"})
def test_load_league_metadata(mock_load):
    assert load_league_metadata() == {"league_id": "123"}
    mock_load.assert_called_once()

@patch("src.utils.cache_utils._save_cache")
@patch("src.utils.cache_utils.FileLock")
def test_save_league_metadata(mock_lock, mock_save):
    save_league_metadata({"league_id": "123"})
    
    # Assert save was called
    mock_save.assert_called_once()
    saved_data = mock_save.call_args[0][0]
    
    # Assert it added a timestamp
    assert "league_id" in saved_data
    assert "last_updated" in saved_data
