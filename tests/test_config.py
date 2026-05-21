import os
import pytest
from src.config import load_config

def test_load_config_missing_league_id(monkeypatch):
    monkeypatch.setattr("src.config.load_dotenv", lambda: None)
    monkeypatch.delenv("LEAGUE_ID", raising=False)
    with pytest.raises(ValueError, match="LEAGUE_ID is not set"):
        load_config()

def test_load_config_success(monkeypatch):
    monkeypatch.setattr("src.config.load_dotenv", lambda: None)
    monkeypatch.setenv("LEAGUE_ID", "nba.l.12345")
    monkeypatch.setenv("NGROK_AUTHTOKEN", "test_token")
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test_secret")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test_access_token")
    monkeypatch.setenv("SERVER_URL", "https://test.ngrok.io")
    
    config = load_config()
    assert config["LEAGUE_ID"] == "nba.l.12345"
    assert config["NGROK_AUTHTOKEN"] == "test_token"
    assert config["LINE_CHANNEL_SECRET"] == "test_secret"
    assert config["LINE_CHANNEL_ACCESS_TOKEN"] == "test_access_token"
    assert config["SERVER_URL"] == "https://test.ngrok.io"
