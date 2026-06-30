import os
import json
import pytest
from unittest.mock import patch, mock_open
from src.config import load_config, current_chat_id

def test_load_config_with_dynamic_override(tmp_path):
    # 測試多聯盟動態配置覆蓋
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data='{"test_chat_id": "88888"}')):
        token = current_chat_id.set("test_chat_id")
        try:
            config = load_config()
            assert config["LEAGUE_ID"] == "88888"
        finally:
            current_chat_id.reset(token)

