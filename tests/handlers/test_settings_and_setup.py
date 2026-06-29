import pytest
from unittest.mock import MagicMock, patch, mock_open
from src.handlers.settings_handler import SettingsHandler
from src.handlers.set_league_id_handler import SetLeagueIdHandler

def test_settings_handler_shows_flex_menu():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()
    
    event = MagicMock()
    config = MagicMock()
    
    # 測試 A: 當 LEAGUE_ID 未設定時，回傳僅含「設置聯盟ID」的選單
    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": None}):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        assert "設置選單" in args[2]

def test_set_league_id_handler_success():
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#設置聯盟ID 12345"
    config = MagicMock()
    
    mock_team = MagicMock()
    mock_team.team_id = "1"
    mock_team.name = "官方測試隊伍"
    
    mock_league = MagicMock()
    mock_league.teams.return_value = [mock_team]
    
    with patch("src.handlers.set_league_id_handler.sync_season_metadata") as mock_sync, \
         patch("src.handlers.set_league_id_handler.open", mock_open()) as mock_file, \
         patch("src.handlers.set_league_id_handler.os.path.exists", return_value=False), \
         patch("yahoofantasy.League", return_value=mock_league) as mock_league_cls:
        handler.execute(event, config)
        
        mock_sync.assert_called_once()
        mock_league_cls.assert_called_once()
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "✅ 成功將此聊天室綁定至聯賽 ID：nba.l.12345"
        )


def test_set_league_id_handler_multi_league_binding():
    from src.config import current_chat_id
    import json
    
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#設置聯盟ID 99999"
    config = MagicMock()
    
    mock_team = MagicMock()
    mock_team.team_id = "1"
    mock_team.name = "官方測試隊伍"
    
    mock_league = MagicMock()
    mock_league.teams.return_value = [mock_team]
    
    # 紀錄 open 寫入的資料
    written_data = {}
    
    import builtins
    import io
    original_open = builtins.open
    
    class MockFile(io.StringIO):
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            val = self.getvalue()
            if val:
                try:
                    nonlocal written_data
                    written_data = json.loads(val)
                except Exception:
                    pass
        def close(self):
            val = self.getvalue()
            if val:
                try:
                    nonlocal written_data
                    written_data = json.loads(val)
                except Exception:
                    pass
            super().close()

    def custom_open(path, mode="r", *args, **kwargs):
        if "chat_league_mapping.json" in str(path).replace("\\", "/"):
            if "r" in mode:
                return MockFile("{}")
            return MockFile()
        return original_open(path, mode, *args, **kwargs)
        
    token = current_chat_id.set("group_abc")
    try:
        with patch("src.handlers.set_league_id_handler.sync_season_metadata") as mock_sync, \
             patch("src.handlers.set_league_id_handler.open", side_effect=custom_open), \
             patch("src.handlers.set_league_id_handler.os.path.exists", return_value=False), \
             patch("yahoofantasy.League", return_value=mock_league) as mock_league_cls:
             
            handler.execute(event, config)
            
            mock_sync.assert_called_once()
            assert written_data.get("group_abc") == "nba.l.99999"
            handler.reply_text.assert_called_once_with(
                event, 
                config, 
                "✅ 成功將此聊天室綁定至聯賽 ID：nba.l.99999"
            )
    finally:
        current_chat_id.reset(token)


def test_set_league_id_handler_interactive_flow(mocker):
    from src.handlers.set_league_id_handler import SetLeagueIdHandler
    from src.utils import session_manager
    
    handler = SetLeagueIdHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_reply_text = mocker.patch.object(handler, "reply_text")
    
    # 測試 1: 傳送 "#設置聯盟ID" (無參數)
    event1 = MagicMock()
    event1.message.text = "#設置聯盟ID"
    event1.source.user_id = "user_test_123"
    
    handler.execute(event1, MagicMock())
    
    # 驗證是否回覆 Flex Message
    mock_reply_flex.assert_called_once()
    flex_msg = mock_reply_flex.call_args[0][3]
    assert flex_msg is not None
    
    # 測試 2: 選擇運動 "#設置聯盟ID nba"
    event2 = MagicMock()
    event2.message.text = "#設置聯盟ID nba"
    event2.source.user_id = "user_test_123"
    
    mock_reply_flex.reset_mock()
    
    handler.execute(event2, MagicMock())
    
    # 驗證是否設定了對話會話 (session_manager)
    session = session_manager.get_session("user_test_123", "set_league_id")
    assert session is not None
    assert session.get("sport") == "nba"
    
    # 驗證回覆了引導提示文字
    mock_reply_text.assert_called_once()
    assert "請在 60 秒內輸入您的聯盟 ID" in mock_reply_text.call_args[0][2]


def test_set_league_id_handler_interactive_session_digit(mocker):
    from src.handlers.set_league_id_handler import SetLeagueIdHandler
    from src.utils import session_manager
    
    handler = SetLeagueIdHandler()
    mock_reply_text = mocker.patch.object(handler, "reply_text")
    
    # 設定一個 active session，使用者已選擇 nba
    session_manager.set_session("user_test_456", "set_league_id", {"sport": "nba"}, duration_sec=60)
    
    # 模擬 IntentRouter 攔截純數字後轉發的事件，也就是 text 變成 "#設置聯盟ID 18457"
    event3 = MagicMock()
    event3.message.text = "#設置聯盟ID 18457"
    event3.source.user_id = "user_test_456"
    
    # Mock sync_season_metadata 與 yahoofantasy
    mock_sync = mocker.patch("src.handlers.set_league_id_handler.sync_season_metadata")
    mock_league = MagicMock()
    mocker.patch("yahoofantasy.League", return_value=mock_league)
    mocker.patch("src.handlers.set_league_id_handler.open", mocker.mock_open())
    mocker.patch("src.handlers.set_league_id_handler.os.path.exists", return_value=True)
    mock_update = mocker.patch.object(handler, "_update_league_id")
    
    handler.execute(event3, MagicMock())
    
    # 驗證 session 是否被清除
    assert session_manager.get_session("user_test_456", "set_league_id") is None
    
    # 驗證傳給 _update_league_id 的 league_id 是 "nba.l.18457"
    mock_update.assert_called_once_with("nba.l.18457")



