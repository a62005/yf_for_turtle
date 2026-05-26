import pytest
import os
from unittest.mock import MagicMock, patch
from src.handlers.stats_handler import StatsHandler
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.reply_token = "dummy_token"
    event.source = MagicMock()
    event.source.user_id = "user123"
    return event

@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
def test_execute_invalid_command(mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    handler = StatsHandler()
    mock_event.message.text = "#未知指令"
    handler.execute(mock_event, mock_config)
    # Should exit early
    mock_api_client.assert_not_called()

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
def test_execute_future_date(mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21"}
    handler = StatsHandler()
    mock_event.message.text = "#戰績20260101" # Future date relative to 2025-11-15
    
    handler.execute(mock_event, mock_config)
    
    # Assert replied with future message
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert reply_req.messages[0].text == "我不是未來人，無法提供未來數據"

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
def test_execute_past_date(mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21"}
    handler = StatsHandler()
    mock_event.message.text = "#戰績20250901" # Before season start
    
    handler.execute(mock_event, mock_config)
    
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert reply_req.messages[0].text == "查無當天數據"

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
def test_execute_out_of_bounds_week(mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21", "end_week": 23}
    handler = StatsHandler()
    mock_event.message.text = "#戰績W24" # Exceeds end_week
    
    handler.execute(mock_event, mock_config)
    
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert reply_req.messages[0].text == "查無當週戰績"

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21", "LEAGUE_ID": "123"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.YahooFantasyFetcher")
def test_execute_lazy_load_week(mock_fetcher, mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21", "end_week": 23}
    
    # Mock the fetcher returning a date
    mock_fetcher.return_value.fetch_week_end_date.return_value = "2025-11-09"
    
    # We just want to see it pass the date validation and try to load the image/cache
    with patch("os.path.exists", return_value=True):
        handler = StatsHandler()
        mock_event.message.text = "#戰績W3" 
        handler.execute(mock_event, mock_config)
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        # It should have tried to send the image, meaning it successfully got the date
        assert hasattr(reply_req.messages[0], 'original_content_url')
        assert "2025-11-09_combined.png" in reply_req.messages[0].original_content_url

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.is_empty_data", return_value=True)
@patch("os.path.exists", return_value=False)
def test_execute_empty_data_cache(mock_exists, mock_is_empty, mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21"}
    handler = StatsHandler()
    mock_event.message.text = "#戰績20251101"
    
    handler.execute(mock_event, mock_config)
    
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert reply_req.messages[0].text == "查無當天數據"

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.get_tw_hour", return_value=10) # Before 14:00
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.is_empty_data", return_value=False)
@patch("os.path.exists", return_value=False)
def test_execute_before_1400(mock_exists, mock_is_empty, mock_messaging_api, mock_api_client, mock_tw_hour, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21", "end_date": "2026-04-05"}
    handler = StatsHandler()
    mock_event.message.text = "#戰績"
    
    handler.execute(mock_event, mock_config)
    
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert reply_req.messages[0].text == "請於 14:00 後再進行查詢。"

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2026-05-01")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("os.path.exists", return_value=True)
def test_execute_offseason_redirection(mock_exists, mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21", "end_date": "2026-04-05", "end_week": 23}
    handler = StatsHandler()
    mock_event.message.text = "#戰績" 
    
    handler.execute(mock_event, mock_config)
    
    # Should redirect to end_date (2026-04-05) instead of today (2026-05-01)
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert "2026-04-05_combined.png" in reply_req.messages[0].original_content_url

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.get_tw_hour", return_value=15)
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.is_empty_data", return_value=False)
@patch("os.path.exists", return_value=False)
@patch("src.handlers.stats_handler.JobTracker")
def test_execute_job_already_running(mock_job_tracker, mock_exists, mock_is_empty, mock_messaging_api, mock_api_client, mock_tw_hour, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21"}
    mock_job_tracker.return_value.add_job.return_value = False # Job already running
    handler = StatsHandler()
    mock_event.message.text = "#戰績"
    
    handler.execute(mock_event, mock_config)
    
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert "稍後將主動通知您" in reply_req.messages[0].text
