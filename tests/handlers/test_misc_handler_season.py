import pytest
from unittest.mock import MagicMock, patch
from src.handlers.misc_handler import MiscHandler

def test_misc_handler_season_start_flow_cache_hit():
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    # 測試從 load_config 讀取 NEXT_SEASON_START_DATE 命中 (且為休賽季)
    with patch("src.handlers.misc_handler.load_config", return_value={"NEXT_SEASON_START_DATE": "2026-10-20 08:00:00"}), \
         patch("src.handlers.misc_handler.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
         patch("src.handlers.misc_handler.get_pacific_date", return_value="2026-05-29"), \
         patch.object(handler, "_calculate_countdown", return_value="10 天 5 小時 30 分鐘"):
        handler.execute(event, config)
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "🏀 新賽季即將開始以下時間開打：\n👉 2026年10月20日\n🏀 距離新賽季開季還有：\n👉 10 天 5 小時 30 分鐘"
        )

def test_misc_handler_season_start_flow_llm_search():
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    meta = {"end_date": "2026-04-12"}
    
    # 無快取時，執行 LLM 搜尋並呼叫 _update_settings_file 寫入 settings.json
    with patch("src.handlers.misc_handler.load_config", return_value={"NEXT_SEASON_START_DATE": None}), \
         patch("src.handlers.misc_handler.load_league_metadata", return_value=meta), \
         patch("src.handlers.misc_handler.get_pacific_date", return_value="2026-05-29"), \
         patch.object(handler, "_update_settings_file") as mock_update, \
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
        mock_update.assert_called_once_with({"next_season_start_date": "2026-10-20 08:00:00"})
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "🏀 新賽季即將開始以下時間開打：\n👉 2026年10月20日\n🏀 距離新賽季開季還有：\n👉 15 天 1 小時 0 分鐘"
        )

def test_misc_handler_season_start_all_failed():
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    meta = {"end_date": "2026-04-12"}
    
    with patch("src.handlers.misc_handler.load_config", return_value={"NEXT_SEASON_START_DATE": None}), \
         patch("src.handlers.misc_handler.load_league_metadata", return_value=meta), \
         patch("src.handlers.misc_handler.get_pacific_date", return_value="2026-05-29"), \
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
