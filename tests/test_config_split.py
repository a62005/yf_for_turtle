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
    league_env.write_text("SEASON_START_DATE=2025-01-01")
    
    private_env = d / ".env"
    private_env.write_text("SEASON_START_DATE=2025-01-02\nYAHOO_CLIENT_ID=secret_token")
    
    # 執行載入
    from unittest.mock import patch
    with patch("os.path.exists", return_value=False):
        config = load_config()
    
    # 驗證覆蓋與合併邏輯
    assert config["LEAGUE_ID"] is None # 環境變數應被忽略
    assert config["SEASON_START_DATE"] == "2025-01-02" # .env 應覆蓋 league.env
    assert config["YAHOO_CLIENT_ID"] == "secret_token" # 來自 .env

def test_load_config_settings_override(monkeypatch):
    # 清除現有的環境變數，避免干擾
    monkeypatch.delenv("LEAGUE_ID", raising=False)
    monkeypatch.delenv("SEASON_START_DATE", raising=False)
    monkeypatch.delenv("DRAFT_DATE", raising=False)
    monkeypatch.delenv("NEXT_SEASON_START_DATE", raising=False)
    
    # 模擬環境變數 (在 dotenv 或環境變數中的初始值)
    monkeypatch.setenv("DRAFT_DATE", "2025-10-10")
    monkeypatch.setenv("NEXT_SEASON_START_DATE", "2025-10-20")

    # 模擬當 settings.json 存在時，自訂的 DRAFT_DATE 與 next_season_start_date
    mock_settings_content = '{"DRAFT_DATE": "2025-11-11", "next_season_start_date": "2025-11-22"}'
    mock_chat_league_mapping_content = '{"test_chat_id": "12345"}'

    from unittest.mock import patch, mock_open
    from src.config import current_chat_id
    import builtins

    # 我們需要讓 os.path.exists 針對特定檔案回傳 True
    original_exists = os.path.exists
    def custom_exists(path):
        normalized_path = path.replace("\\", "/")
        if "data/security/chat_league_mapping.json" in normalized_path:
            return True
        if "data/league/12345/settings.json" in normalized_path:
            return True
        return False

    def custom_open(path, *args, **kwargs):
        normalized_path = path.replace("\\", "/")
        if "data/security/chat_league_mapping.json" in normalized_path:
            return mock_open(read_data=mock_chat_league_mapping_content)()
        if "data/league/12345/settings.json" in normalized_path:
            return mock_open(read_data=mock_settings_content)()
        return mock_open()()

    with patch("os.path.exists", side_effect=custom_exists):
        with patch("builtins.open", side_effect=custom_open):
            token = current_chat_id.set("test_chat_id")
            try:
                config = load_config()
            finally:
                current_chat_id.reset(token)

    # 驗證 settings.json 的自訂值覆寫了環境變數的值
    assert config["LEAGUE_ID"] == "12345"
    assert config["DRAFT_DATE"] == "2025-11-11"
    assert config["NEXT_SEASON_START_DATE"] == "2025-11-22"


