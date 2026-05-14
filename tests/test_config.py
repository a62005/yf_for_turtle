import os
import pytest
from src.config import load_config

def test_load_config_missing_league_id(monkeypatch):
    monkeypatch.delenv("LEAGUE_ID", raising=False)
    with pytest.raises(ValueError, match="LEAGUE_ID is not set"):
        load_config()

def test_load_config_success(monkeypatch):
    monkeypatch.setenv("LEAGUE_ID", "nba.l.12345")
    config = load_config()
    assert config["LEAGUE_ID"] == "nba.l.12345"
