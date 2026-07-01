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
    
    # Patch is_stats_query_allowed to return allowed=True so the time-limit block is bypassed
    with patch("src.utils.time_utils.is_stats_query_allowed", return_value=(True, "")), \
         patch("src.handlers.stats_handler.get_target_date", return_value="2024-11-01"):
        handler.execute(event, config)
    
    # Check if MessagingApi was called (at least once for "數據更新中")
    assert mock_messaging_api.called
    # Check if subprocess.Popen was called to trigger main.py
    assert mock_popen.called


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
def test_stats_handler_mlb_bypasses_game_day(mock_os_close, mock_os_open, mock_makedirs, mock_exists, mock_popen, mock_messaging_api, mock_api_client, mock_is_empty_data, mock_get_pacific, mock_load_meta, mock_load_config):
    handler = StatsHandler()
    
    # MLB league_id
    mock_load_config.return_value = {"LEAGUE_ID": "mlb.l.12345", "DEFAULT_SEASON_START": "2024-10-22"}
    mock_load_meta.return_value = {"start_date": "2024-10-22", "end_date": "2025-04-13", "end_week": 24}
    mock_get_pacific.return_value = "2024-11-01"
    mock_exists.return_value = False
    mock_is_empty_data.return_value = False
    
    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"
    
    config = MagicMock(spec=Configuration)
    
    # 因為是 MLB，所以不論目前時間是幾點、NBA 是否在比賽，都不應被 is_stats_query_allowed 阻擋，直接放行
    with patch("src.handlers.stats_handler.get_target_date", return_value="2024-11-01"), \
         patch("src.utils.time_utils.is_game_day", return_value=(True, "")):
        handler.execute(event, config)
        
    # 因為是 MLB，所以不應被 is_stats_query_allowed 阻擋，依然能觸發背景任務
    assert mock_popen.called
    assert mock_messaging_api.called


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date")
@patch("src.handlers.stats_handler.is_empty_data")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.subprocess.Popen")
@patch("os.path.exists")
def test_stats_handler_mlb_cache_hit(mock_exists, mock_popen, mock_messaging_api, mock_api_client, mock_is_empty_data, mock_get_pacific, mock_load_meta, mock_load_config, monkeypatch):
    handler = StatsHandler()
    
    # MLB league_id
    mock_load_config.return_value = {
        "LEAGUE_ID": "mlb.l.62358",
        "DEFAULT_SEASON_START": "2024-10-22",
        "SERVER_URL": "http://localhost:5000"
    }
    mock_load_meta.return_value = {"start_date": "2024-10-22", "end_date": "2025-04-13", "end_week": 24}
    mock_get_pacific.return_value = "2024-11-01"
    
    monkeypatch.setenv("SERVER_URL", "http://localhost:5000")
    
    mock_exists.return_value = True
    mock_is_empty_data.return_value = False
    
    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"
    
    config = MagicMock(spec=Configuration)
    
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance
    
    with patch("src.handlers.stats_handler.get_target_date", return_value="2024-11-01"):
        handler.execute(event, config)
    
    # verify that MessagingApi was called and Popen was NOT called (because of cache hit)
    assert not mock_popen.called
    assert mock_messaging_api.called
    
    call_args = mock_api_instance.reply_message.call_args
    assert call_args is not None
    reply_request = call_args[0][0]
    
    messages = reply_request.messages
    assert len(messages) == 2
    
    assert messages[0].original_content_url == "https://localhost:5000/images/mlb/62358/2024-11-01_combined_hitter.png"
    assert messages[0].preview_image_url == "https://localhost:5000/images/mlb/62358/2024-11-01_combined_hitter.png"
    assert messages[1].original_content_url == "https://localhost:5000/images/mlb/62358/2024-11-01_combined_pitcher.png"
    assert messages[1].preview_image_url == "https://localhost:5000/images/mlb/62358/2024-11-01_combined_pitcher.png"

