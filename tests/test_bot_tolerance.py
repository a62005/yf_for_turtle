import os
import json
import pytest
from unittest.mock import patch, mock_open
from src.config import load_config

def test_load_config_with_dynamic_override(tmp_path):
    # 測試配置覆蓋優先權
    sec_dir = tmp_path / "data" / "security"
    sec_dir.mkdir(parents=True)
    config_file = sec_dir / "league_config.json"
    
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump({"LEAGUE_ID": "88888"}, f)
        
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data='{"LEAGUE_ID": "88888"}')):
        config = load_config()
        assert config["LEAGUE_ID"] == "88888"
