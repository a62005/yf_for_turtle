import pytest
from unittest.mock import MagicMock, patch
from src.handlers.misc_handler import MiscHandler

def test_misc_handler_season_start_flow_cache_hit():
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    meta = {"next_season_start_date": "2026-10-20 08:00:00"}
    
    with patch("src.handlers.misc_handler.load_league_metadata", return_value=meta), \
         patch.object(handler, "_calculate_countdown", return_value="10 天 5 小時 30 分鐘"):
        handler.execute(event, config)
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "🏀 距離新賽季開季還有：\n👉 10 天 5 小時 30 分鐘"
        )

def test_misc_handler_season_start_flow_llm_search():
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    meta = {}
    
    with patch("src.handlers.misc_handler.load_league_metadata", return_value=meta), \
         patch("src.handlers.misc_handler.save_league_metadata") as mock_save, \
         patch("src.handlers.misc_handler.LLMAgent") as mock_agent_class, \
         patch.object(handler, "_calculate_countdown", return_value="15 天 1 小時 0 分鐘"):
         
        mock_agent = MagicMock()
        mock_agent.search_nba_season_start.return_value = {
            "success": True, 
            "start_date": "2026-10-20 08:00:00"
        }
        mock_agent_class.return_value = mock_agent
        
        handler.execute(event, config)
        
        mock_agent.search_nba_season_start.assert_called_once()
        mock_save.assert_called_once()
        assert meta["next_season_start_date"] == "2026-10-20 08:00:00"
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "🏀 距離新賽季開季還有：\n👉 15 天 1 小時 0 分鐘"
        )

def test_misc_handler_season_start_all_failed():
    handler = MagicMock() # 用 MagicMock 以便測試 _handle_season_start 內部
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    meta = {}
    
    with patch("src.handlers.misc_handler.load_league_metadata", return_value=meta), \
         patch("src.handlers.misc_handler.LLMAgent") as mock_agent_class:
         
        mock_agent = MagicMock()
        mock_agent.search_nba_season_start.return_value = {"success": False, "start_date": None}
        mock_agent_class.return_value = mock_agent
        
        handler.execute(event, config)
        
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "🏀 無法獲取新賽季開季時間"
        )
