import os
import pytest
from src.config import load_config

def test_load_config_missing_league_id(monkeypatch):
    monkeypatch.setattr("src.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("LEAGUE_ID", raising=False)
    with pytest.raises(ValueError, match="LEAGUE_ID is not set"):
        load_config()

def test_load_config_success(monkeypatch):
    monkeypatch.setattr("src.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("LEAGUE_ID", "nba.l.12345")
    monkeypatch.setenv("LLM_API_KEY", "test_api_key")
    monkeypatch.setenv("LLM_MODEL", "test_model")
    monkeypatch.delenv("ENABLE_FOOTBALL_ANALYSIS", raising=False)
    config = load_config()
    assert config["LEAGUE_ID"] == "nba.l.12345"
    assert config["LLM_API_KEY"] == "test_api_key"
    assert config["LLM_MODEL"] == "test_model"
    assert config["ENABLE_FOOTBALL_ANALYSIS"] is False

    monkeypatch.setenv("ENABLE_FOOTBALL_ANALYSIS", "true")
    config = load_config()
    assert config["ENABLE_FOOTBALL_ANALYSIS"] is True
