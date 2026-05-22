import os
from src.config import load_config
import pytest

def test_config_load_priority(tmp_path, monkeypatch):
    # 清除現有的環境變數，避免干擾
    monkeypatch.delenv("LEAGUE_ID", raising=False)
    monkeypatch.delenv("SEASON_START_DATE", raising=False)
    monkeypatch.delenv("YAHOO_CLIENT_ID", raising=False)
    monkeypatch.delenv("TEAM_MAPPING_FILE", raising=False)
    monkeypatch.delenv("YAHOO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("NGROK_AUTHTOKEN", raising=False)
    monkeypatch.delenv("LINE_CHANNEL_SECRET", raising=False)
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SERVER_URL", raising=False)

    # 模擬根目錄
    d = tmp_path / "project"
    d.mkdir()
    monkeypatch.chdir(d)
    
    # 建立測試用的 env 檔案
    league_env = d / "league.env"
    league_env.write_text("LEAGUE_ID=123\nSEASON_START_DATE=2025-01-01")
    
    private_env = d / ".env"
    private_env.write_text("LEAGUE_ID=456\nYAHOO_CLIENT_ID=secret_token")
    
    # 執行載入
    config = load_config()
    
    # 驗證覆蓋與合併邏輯
    assert config["LEAGUE_ID"] == "456" # .env 應覆蓋 league.env
    assert config["SEASON_START_DATE"] == "2025-01-01" # 來自 league.env
    assert config["YAHOO_CLIENT_ID"] == "secret_token" # 來自 .env
