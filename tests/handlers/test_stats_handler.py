import pytest
from unittest.mock import MagicMock, patch
from src.handlers.stats_handler import StatsHandler
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

def test_stats_handler_can_handle():
    handler = StatsHandler()
    assert handler.can_handle("#戰績") is True
    assert handler.can_handle("#戰績昨天") is True
    assert handler.can_handle("#戰績上週") is True
    assert handler.can_handle("#戰績W23") is True
    assert handler.can_handle("#戰績w23") is True
    assert handler.can_handle("#戰績20250101") is True
    
    assert handler.can_handle("#當天戰績") is False
    assert handler.can_handle("#當週戰績") is False
    assert handler.can_handle("#獎金") is False
    assert handler.can_handle("戰績") is False

def test_stats_handler_parse_command():
    handler = StatsHandler()
    assert handler.parse_command("#戰績") == ("combined", None)
    assert handler.parse_command("#戰績昨天") == ("yesterday", None)
    assert handler.parse_command("#戰績上週") == ("last_week", None)
    assert handler.parse_command("#戰績W23") == ("specific_week", 23)
    assert handler.parse_command("#戰績w23") == ("specific_week", 23)
    assert handler.parse_command("#戰績20250101") == ("specific_date", "2025-01-01")
    assert handler.parse_command("#無效") == (None, None)

@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date")
@patch("src.handlers.stats_handler.is_empty_data")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.subprocess.Popen")
@patch("os.path.exists")
@patch("os.makedirs")
@patch("os.open")
@patch("os.close")
def test_stats_handler_execute_sanity(mock_os_close, mock_os_open, mock_makedirs, mock_exists, mock_popen, mock_messaging_api, mock_api_client, mock_is_empty_data, mock_get_pacific, mock_load_meta, mock_load_config):
    handler = StatsHandler()
    
    # Setup mocks
    mock_load_config.return_value = {"DEFAULT_SEASON_START": "2024-10-22"}
    mock_load_meta.return_value = {"start_date": "2024-10-22", "end_date": "2025-04-13", "end_week": 24}
    mock_get_pacific.return_value = "2024-11-01"
    mock_exists.return_value = False # Image does not exist
    mock_is_empty_data.return_value = False # Data is not marked empty
    
    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"
    
    config = MagicMock(spec=Configuration)
    
    # Patch get_tw_hour to simulate a time after 14:00 so the "請於 14:00 後再進行查詢。" block is bypassed
    with patch("src.handlers.stats_handler.get_tw_hour", return_value=15):
        handler.execute(event, config)
    
    # Check if MessagingApi was called (at least once for "數據更新中")
    assert mock_messaging_api.called
    # Check if subprocess.Popen was called to trigger main.py
    assert mock_popen.called
