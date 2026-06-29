import pytest
from unittest.mock import MagicMock
from src.llm.llm_agent import LLMAgent

def test_llm_agent_search_nba_season_start_success():
    agent = LLMAgent()
    
    # Mock Provider 支援搜尋且成功回傳
    mock_provider = MagicMock()
    mock_provider.generate_json_with_search.return_value = {
        "success": True, 
        "start_date": "2026-10-20 08:00:00"
    }
    agent.provider = mock_provider
    
    res = agent.search_nba_season_start(2026)
    assert res == {"success": True, "start_date": "2026-10-20 08:00:00"}
    mock_provider.generate_json_with_search.assert_called_once()

def test_llm_agent_search_nba_season_start_unsupported():
    agent = LLMAgent()
    
    # Mock Provider 不支援搜尋方法 (例如空 spec 或是沒有該屬性)
    agent.provider = MagicMock(spec=[])
    
    res = agent.search_nba_season_start(2026)
    assert res == {"success": False, "start_date": None}

def test_llm_agent_search_nba_season_start_fallback():
    agent = LLMAgent()
    
    # Mock Provider 支援搜尋但拋出異常 (例如 429)
    mock_provider = MagicMock()
    mock_provider.generate_json_with_search.side_effect = Exception("429 Too Many Requests")
    mock_provider.generate_json.return_value = {
        "success": True, 
        "start_date": "2026-10-20 08:00:00"
    }
    agent.provider = mock_provider
    
    res = agent.search_nba_season_start(2026)
    assert res == {"success": True, "start_date": "2026-10-20 08:00:00"}
    mock_provider.generate_json_with_search.assert_called_once()
    mock_provider.generate_json.assert_called_once()
