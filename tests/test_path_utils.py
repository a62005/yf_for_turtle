import os
import pytest
from unittest.mock import patch
from src.utils.path_utils import (
    get_league_id, 
    get_league_dir, 
    get_league_metadata_path,
    get_league_team_mapping_path
)

def test_path_utils_dynamic_routing():
    # 測試 A: 當 config 中沒有 LEAGUE_ID 時
    with patch("src.utils.path_utils.load_config", return_value={}):
        assert get_league_id() is None
        assert "default" in get_league_dir()
        
    # 測試 B: 當 config 中有 LEAGUE_ID 時，返回正確物理隔離路徑
    with patch("src.utils.path_utils.load_config", return_value={"LEAGUE_ID": "99999"}):
        assert get_league_id() == "99999"
        assert get_league_dir().replace("\\", "/").endswith("data/league/99999")
        assert get_league_metadata_path().replace("\\", "/").endswith("data/league/99999/metadata.json")
        assert get_league_team_mapping_path().replace("\\", "/").endswith("data/league/99999/team_mapping.json")
