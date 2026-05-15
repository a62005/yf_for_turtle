# tests/test_storage.py
import os
import json
import pytest
from src.storage import JsonStorage

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
