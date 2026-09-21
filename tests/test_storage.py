# tests/test_storage.py
import os
import json
import pytest
from unittest.mock import patch
from src.storage import JsonStorage
from src.utils.audit_logger import get_audit_log_path

def test_json_storage_saves_data(tmp_path):
    # tmp_path is a pytest fixture providing a temporary directory unique to the test invocation
    data_dir = tmp_path / "data"
    storage = JsonStorage(data_dir=str(data_dir))
    
    test_data = {"teams": [{"name": "Team A"}]}
    filename = storage.save(test_data, "test_league")
    
    assert os.path.exists(filename)
    with open(filename, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data == test_data

def test_json_storage_saves_to_subdir(tmp_path):
    data_dir = tmp_path / "data"
    storage = JsonStorage(data_dir=str(data_dir))
    test_data = {"key": "value"}
    sub_dir = "weekly"
    
    filepath = storage.save(test_data, "test_file", sub_dir=sub_dir)
    
    assert os.path.join(str(data_dir), sub_dir) in filepath
    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        assert json.load(f) == test_data

def test_json_storage_overwrite(tmp_path):
    data_dir = tmp_path / "data"
    storage = JsonStorage(data_dir=str(data_dir))
    test_data_1 = {"version": 1}
    test_data_2 = {"version": 2}
    identifier = "season_stats"
    
    # First save
    path1 = storage.save(test_data_1, identifier, overwrite=True)
    # Second save with same identifier and overwrite=True
    path2 = storage.save(test_data_2, identifier, overwrite=True)
    
    assert path1 == path2
    assert os.path.exists(path1)
    with open(path1, "r") as f:
        assert json.load(f) == test_data_2

def test_json_storage_audit_logging_and_delete(tmp_path):
    data_dir = tmp_path / "data"
    test_logs_dir = tmp_path / "logs"
    
    with patch("src.utils.path_utils.LOGS_DIR", str(test_logs_dir)):
        storage = JsonStorage(data_dir=str(data_dir))
        
        # 1. 寫入檔案
        path = storage.save({"score": 100}, "game_result", overwrite=True)
        assert os.path.exists(path)
        
        log_file = get_audit_log_path()
        assert os.path.exists(log_file)
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "action=CREATE" in content
            assert "game_result.json" in content
            
        # 2. 刪除檔案
        deleted = storage.delete("game_result")
        assert deleted is True
        assert not os.path.exists(path)
        
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "action=DELETE" in content
