import pytest
from src.config import load_config, current_chat_id
from unittest.mock import patch, mock_open
import json

def test_load_config_with_different_chat_ids():
    mapping_data = {
        "chat_123": "league_abc",
        "chat_456": "league_xyz"
    }
    fake_json = json.dumps(mapping_data)
    
    # 模擬 mapping 檔案存在，並且讓其他 os.path.exists 返回原本的值或 False
    def mock_exists(path):
        if "chat_league_mapping.json" in path:
            return True
        return False
        
    with patch("os.path.exists", side_effect=mock_exists), \
         patch("builtins.open", mock_open(read_data=fake_json)):
        
        # 情境 1: chat_id 為 chat_123
        token1 = current_chat_id.set("chat_123")
        try:
            config1 = load_config()
            assert config1["LEAGUE_ID"] == "league_abc"
        finally:
            current_chat_id.reset(token1)
            
        # 情境 2: chat_id 為 chat_456
        token2 = current_chat_id.set("chat_456")
        try:
            config2 = load_config()
            assert config2["LEAGUE_ID"] == "league_xyz"
        finally:
            current_chat_id.reset(token2)

        # 情境 3: chat_id 為未綁定的 chat_789
        token3 = current_chat_id.set("chat_789")
        try:
            config3 = load_config()
            assert config3["LEAGUE_ID"] is None
        finally:
            current_chat_id.reset(token3)

        # 情境 4: chat_id 為 None 或未設定
        config4 = load_config()
        assert config4["LEAGUE_ID"] is None
