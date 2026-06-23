import os
import pytest
from unittest.mock import MagicMock, patch
from main import main

@patch("main.load_config")
@patch("main.YahooFantasyFetcher")
@patch("main.JsonStorage")
@patch("main.process_stats_for_visual")
@patch("main.render_stats_html")
@patch("main.capture_html_to_png")
@patch("linebot.v3.messaging.ApiClient")
@patch("linebot.v3.messaging.MessagingApi")
def test_main_push_success(
    mock_messaging_api,
    mock_api_client,
    mock_capture_html_to_png,
    mock_render_stats_html,
    mock_process_stats_for_visual,
    mock_json_storage,
    mock_fetcher_class,
    mock_load_config,
    tmp_path,
    monkeypatch
):
    # Setup lock file environment
    lock_file = tmp_path / "test.lock"
    lock_file.touch()
    assert lock_file.exists()
    
    monkeypatch.setenv("FETCH_LOCK_PATH", str(lock_file))
    monkeypatch.setenv("LINE_REPLY_TO", "test_user_id")
    monkeypatch.setenv("TEST_DATE", "2026-01-18")
    monkeypatch.setenv("TEST_WEEK", "13")
    
    # Mock config load
    mock_load_config.return_value = {
        "LEAGUE_ID": "12345",
        "LINE_CHANNEL_ACCESS_TOKEN": "mock_token",
        "SERVER_URL": "http://mock-server.com"
    }
    
    # Mock fetcher
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_team_stats.return_value = {}
    mock_fetcher.fetch_weekly_stats.return_value = {}
    mock_fetcher.fetch_daily_stats.return_value = {"team_stats": []}
    mock_fetcher.fetch_batch_rosters.return_value = {}
    mock_fetcher_class.return_value = mock_fetcher
    
    # Mock storage
    mock_storage = MagicMock()
    mock_json_storage.return_value = mock_storage
    
    # Execute main
    main()
    
    # Verify lock file is cleaned up
    assert not lock_file.exists()
    
    # Verify push_message was called with the combined image URL
    mock_messaging_api.return_value.push_message.assert_called_once()
    push_req = mock_messaging_api.return_value.push_message.call_args[0][0]
    assert push_req.to == "test_user_id"
    assert push_req.messages[0].original_content_url == "https://mock-server.com/images/2026-01-18_combined.png"


@patch("main.load_config")
@patch("main.YahooFantasyFetcher")
@patch("main.JsonStorage")
@patch("main.process_stats_for_visual")
@patch("main.render_stats_html")
@patch("main.capture_html_to_png")
@patch("linebot.v3.messaging.ApiClient")
@patch("linebot.v3.messaging.MessagingApi")
def test_main_push_failure_still_cleans_lock(
    mock_messaging_api,
    mock_api_client,
    mock_capture_html_to_png,
    mock_render_stats_html,
    mock_process_stats_for_visual,
    mock_json_storage,
    mock_fetcher_class,
    mock_load_config,
    tmp_path,
    monkeypatch
):
    lock_file = tmp_path / "test.lock"
    lock_file.touch()
    assert lock_file.exists()
    
    monkeypatch.setenv("FETCH_LOCK_PATH", str(lock_file))
    monkeypatch.setenv("LINE_REPLY_TO", "test_user_id")
    
    # Mock config load
    mock_load_config.return_value = {
        "LEAGUE_ID": "12345",
        "LINE_CHANNEL_ACCESS_TOKEN": "mock_token"
    }
    
    # Simulate fetcher crash
    mock_fetcher_class.side_effect = Exception("Yahoo API Error")
    
    # Execute main expecting it to raise Exception
    with pytest.raises(Exception, match="Yahoo API Error"):
        main()
        
    # Verify lock file is cleaned up
    assert not lock_file.exists()
    
    # Verify push_message was called to notify about the failure
    mock_messaging_api.return_value.push_message.assert_called_once()
    push_req = mock_messaging_api.return_value.push_message.call_args[0][0]
    assert push_req.to == "test_user_id"
    assert "戰績數據更新失敗" in push_req.messages[0].text
