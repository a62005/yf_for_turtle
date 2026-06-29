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
            "✅ 成功將此聊天室綁定至聯賽 ID：12345"
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
            assert written_data.get("group_abc") == "99999"
            handler.reply_text.assert_called_once_with(
                event, 
                config, 
                "✅ 成功將此聊天室綁定至聯賽 ID：99999"
            )
    finally:
        current_chat_id.reset(token)


