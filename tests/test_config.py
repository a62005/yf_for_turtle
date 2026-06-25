import os
import pytest
from src.config import load_config

def test_load_config_missing_league_id(monkeypatch):
    monkeypatch.setattr("src.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("LEAGUE_ID", raising=False)
    config = load_config()
    assert config["LEAGUE_ID"] is None


def test_load_config_success(monkeypatch):
    monkeypatch.setattr("src.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("LEAGUE_ID", "nba.l.12345")
    monkeypatch.setenv("LLM_API_KEY", "test_api_key")
    monkeypatch.setenv("LLM_MODEL", "test_model")
    monkeypatch.delenv("ENABLE_FOOTBALL_ANALYSIS", raising=False)
    config = load_config()
    assert config["LEAGUE_ID"] is None  # 環境變數的 LEAGUE_ID 應被忽略
    assert config["LLM_API_KEY"] == "test_api_key"
    assert config["LLM_MODEL"] == "test_model"
    assert config["ENABLE_FOOTBALL_ANALYSIS"] is False

    monkeypatch.setenv("ENABLE_FOOTBALL_ANALYSIS", "true")
    config = load_config()
    assert config["ENABLE_FOOTBALL_ANALYSIS"] is True


def test_load_config_from_dynamic_json(monkeypatch):
    monkeypatch.setattr("src.config.load_dotenv", lambda *args, **kwargs: None)
    
    # 使用 mock_open 模擬讀取 data/security/league_config.json
    from unittest.mock import patch, mock_open
    import json
    
    fake_json = json.dumps({"LEAGUE_ID": "88888"})
    
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=fake_json)):
        config = load_config()
        assert config["LEAGUE_ID"] == "88888"
