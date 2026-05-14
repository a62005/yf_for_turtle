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
