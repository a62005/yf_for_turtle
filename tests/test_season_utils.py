import os
import json
from src.cache_utils import save_league_metadata, load_league_metadata
from datetime import datetime

def test_metadata_cache(tmp_path, monkeypatch):
    test_file = tmp_path / "metadata.json"
    monkeypatch.setattr("src.cache_utils.METADATA_FILE", str(test_file))
    
    data = {"start_date": "2025-10-21", "end_date": "2026-04-05"}
    save_league_metadata(data)
    
    loaded = load_league_metadata()
    assert loaded["start_date"] == "2025-10-21"
    assert "last_updated" in loaded
