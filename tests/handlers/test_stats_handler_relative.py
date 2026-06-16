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
    return event

@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21", "LEAGUE_ID": "123"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.YahooFantasyFetcher")
def test_execute_yesterday(mock_fetcher, mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21"}
    
    with patch("os.path.exists", return_value=True):
        handler = StatsHandler()
        mock_event.message.text = "#戰績昨天" 
        handler.execute(mock_event, mock_config)
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert "2025-11-14_combined.png" in reply_req.messages[0].original_content_url

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21", "LEAGUE_ID": "123"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15") # This is a Saturday in Week 3
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.YahooFantasyFetcher")
def test_execute_last_week(mock_fetcher, mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    # Setup metadata to have cached week dates
    mock_load_meta.return_value = {
        "start_date": "2025-10-21",
        "date_to_week": {"2025-11-15": 3},
        "week_dates": {"2": "2025-11-02"}
    }
    
    with patch("os.path.exists", return_value=True):
        handler = StatsHandler()
        mock_event.message.text = "#戰績上週" 
        handler.execute(mock_event, mock_config)
        
        # It should resolve target_week=2, and look up the end date from week_dates = "2025-11-02"
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert "2025-11-02_combined.png" in reply_req.messages[0].original_content_url
        
@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21", "LEAGUE_ID": "123"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.YahooFantasyFetcher")
@patch("src.handlers.stats_handler.save_league_metadata")
def test_get_week_end_date_fallback(mock_save_meta, mock_fetcher, mock_messaging_api, mock_api_client, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    # Metadata missing week_dates completely
    mock_load_meta.return_value = {"start_date": "2025-10-21", "end_week": 23}
    
    # Mock the fetcher returning a date
    mock_fetcher.return_value.fetch_week_end_date.return_value = "2025-11-09"
    
    with patch("os.path.exists", return_value=True):
        handler = StatsHandler()
        mock_event.message.text = "#戰績W3" 
        handler.execute(mock_event, mock_config)
        
        # Should have called fetcher
        mock_fetcher.return_value.fetch_week_end_date.assert_called_once_with("123", 3)
