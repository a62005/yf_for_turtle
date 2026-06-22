import pytest
from unittest.mock import MagicMock
from linebot.v3.webhooks import MessageEvent, MessageContent
from linebot.v3.messaging import Configuration

from src.handlers.football_handler import FootballHandler

def test_football_handler_can_handle_disabled(monkeypatch):
    # 當 ENABLE_FOOTBALL_ANALYSIS 為 False 時，不響應
    monkeypatch.setattr("src.handlers.football_handler.load_config", lambda: {
        "ENABLE_FOOTBALL_ANALYSIS": False
    })
    
    handler = FootballHandler()
    assert handler.can_handle("#足球 巴西 德國") is False
    assert handler.can_handle("#足球 巴西vs德國") is False

def test_football_handler_can_handle_enabled(monkeypatch):
    # 當 ENABLE_FOOTBALL_ANALYSIS 為 True 時，支援靈活匹配各種分隔符
    monkeypatch.setattr("src.handlers.football_handler.load_config", lambda: {
        "ENABLE_FOOTBALL_ANALYSIS": True
    })
    
    handler = FootballHandler()
    
    # 測試匹配案例
    assert handler.can_handle("#足球 巴西 德國") is True
    assert handler.can_handle("#足球 巴西vs德國") is True
    assert handler.can_handle("#足球 巴西VS德國") is True
    assert handler.can_handle("#足球 巴西 對 德國") is True
    assert handler.can_handle("#足球 巴西 對戰 德國") is True
    assert handler.can_handle("#足球 巴西  德國") is True

def test_football_handler_can_handle_invalid_teams(monkeypatch):
    monkeypatch.setattr("src.handlers.football_handler.load_config", lambda: {
        "ENABLE_FOOTBALL_ANALYSIS": True
    })
    handler = FootballHandler()
    assert handler.can_handle("#足球 金州勇士 富邦勇士") is False
    assert handler.can_handle("#足球 德國 紐約尼克") is False
    assert handler.can_handle("#足球 巴西 德國") is True


def test_football_handler_can_handle_no_io_on_mismatch(mocker):
    # 測試不匹配的案例不會觸發 load_config 讀取磁碟
    mock_load = mocker.patch("src.handlers.football_handler.load_config")
    
    handler = FootballHandler()
    
    # 不匹配的案例
    assert handler.can_handle("#足球 巴西") is False
    assert handler.can_handle("#對戰 巴西") is False
    assert handler.can_handle("巴西 德國") is False
    
    # 驗證 load_config 從未被呼叫過
    mock_load.assert_not_called()

def test_football_handler_execute_success(monkeypatch, mocker):
    # 測試 execute 是否正確提取兩隊、呼叫分析器並回覆
    monkeypatch.setattr("src.handlers.football_handler.load_config", lambda: {
        "ENABLE_FOOTBALL_ANALYSIS": True
    })
    
    # Mock analyze_football_matchup 函數
    mock_analyze = mocker.patch(
        "src.handlers.football_handler.analyze_football_matchup",
        return_value="這是測試的足球對戰分析結果"
    )
    
    handler = FootballHandler()
    
    # 建立 mock MessageEvent
    mock_event = MagicMock(spec=MessageEvent)
    mock_event.reply_token = "dummy_reply_token"
    mock_event.message = MagicMock(spec=MessageContent)
    mock_event.message.text = "#足球 巴西 對戰 德國"
    
    mock_configuration = MagicMock(spec=Configuration)
    
    # Mock FootballHandler.reply_text 方法，用來驗證
    mock_reply_text = mocker.patch.object(handler, "reply_text")
    
    handler.execute(mock_event, mock_configuration)
    
    # 驗證 analyze_football_matchup 有被正確調用，傳入巴西與德國
    mock_analyze.assert_called_once_with("巴西", "德國")
    
    # 驗證 reply_text 發送了兩則訊息
    mock_reply_text.assert_called_once_with(
        mock_event,
        mock_configuration,
        "🔍 正在為您分析 巴西 與 德國 的對戰，請稍候...",
        "這是測試的足球對戰分析結果"
    )
