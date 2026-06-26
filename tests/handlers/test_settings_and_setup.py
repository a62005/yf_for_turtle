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
            "✅ 聯盟 ID 設置成功，並已完成賽季資訊同步！"
        )

