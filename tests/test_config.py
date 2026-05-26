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
    config = load_config()
    assert config["LEAGUE_ID"] == "nba.l.12345"

def test_load_config_cloud_env(monkeypatch):
    monkeypatch.setattr("src.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("LEAGUE_ID", "123")
    config = load_config()
    assert config["ENV"] == "production"
    assert config["STORAGE_TYPE"] == "gcs"
    assert config["TASK_MODE"] == "pubsub"

def test_load_config_local_env(monkeypatch):
    monkeypatch.setattr("src.config.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("LEAGUE_ID", "123")
    config = load_config()
    assert config["ENV"] == "local"
    assert config["STORAGE_TYPE"] == "local"
    assert config["TASK_MODE"] == "subprocess"
