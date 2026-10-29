import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import pytz
from src.handlers.stats_handler import StatsHandler
from src.utils.time_utils import get_stats_rule_date
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ImageMessage, TextMessage


def test_stats_handler_can_handle_only_zhanji():
    handler = StatsHandler()
    assert handler.can_handle("#戰績") is True
    assert handler.can_handle("  #戰績  ") is True
    
    # 暫時移除其他特定天數查詢
    assert handler.can_handle("#戰績昨天") is False
    assert handler.can_handle("#戰績上週") is False
    assert handler.can_handle("#戰績W23") is False
    assert handler.can_handle("#戰績w23") is False
    assert handler.can_handle("#戰績20250101") is False
    assert handler.can_handle("#當天戰績") is False
    assert handler.can_handle("戰績") is False


def test_stats_handler_parse_command():
    handler = StatsHandler()
    assert handler.parse_command("#戰績") == ("combined", None)
    assert handler.parse_command("#戰績昨天") == (None, None)
    assert handler.parse_command("#無效") == (None, None)


def test_get_stats_rule_date():
    tw_tz = pytz.timezone("Asia/Taipei")
    
    # 10/27 10:30 (14:00 前) -> 10/26
    dt_before = tw_tz.localize(datetime(2026, 10, 27, 10, 30))
    assert get_stats_rule_date(dt_before) == "2026-10-26"

    # 10/27 13:59 (14:00 前) -> 10/26
    dt_just_before = tw_tz.localize(datetime(2026, 10, 27, 13, 59))
    assert get_stats_rule_date(dt_just_before) == "2026-10-26"

    # 10/27 14:00 (14:00 當刻) -> 10/27
    dt_exact = tw_tz.localize(datetime(2026, 10, 27, 14, 0))
    assert get_stats_rule_date(dt_exact) == "2026-10-27"

    # 10/27 14:01 (14:00 後) -> 10/27
    dt_after = tw_tz.localize(datetime(2026, 10, 27, 14, 1))
    assert get_stats_rule_date(dt_after) == "2026-10-27"


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("os.path.exists")
def test_stats_handler_nba_image_hit(mock_exists, mock_messaging_api, mock_api_client, mock_load_config, monkeypatch):
    handler = StatsHandler()
    mock_load_config.return_value = {
        "LEAGUE_ID": "nba.l.49432",
        "SERVER_URL": "http://localhost:5000"
    }
    monkeypatch.setenv("SERVER_URL", "http://localhost:5000")
    mock_exists.return_value = True

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"

    config = MagicMock(spec=Configuration)
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance

    with patch("src.handlers.stats_handler.get_stats_rule_date", return_value="2026-10-26"):
        handler.execute(event, config)

    assert mock_messaging_api.called
    call_args = mock_api_instance.reply_message.call_args
    assert call_args is not None
    reply_request = call_args[0][0]
    messages = reply_request.messages
    assert len(messages) == 2
    assert isinstance(messages[0], TextMessage)
    assert messages[0].text == "戰績數據日期：2026-10-26"
    assert isinstance(messages[1], ImageMessage)
    assert "2026-10-26_combined.png" in messages[1].original_content_url


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("os.path.exists")
def test_stats_handler_mlb_image_hit(mock_exists, mock_messaging_api, mock_api_client, mock_load_config, monkeypatch):
    handler = StatsHandler()
    mock_load_config.return_value = {
        "LEAGUE_ID": "mlb.l.62358",
        "SERVER_URL": "http://localhost:5000"
    }
    monkeypatch.setenv("SERVER_URL", "http://localhost:5000")
    mock_exists.return_value = True

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"

    config = MagicMock(spec=Configuration)
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance

    with patch("src.handlers.stats_handler.get_stats_rule_date", return_value="2026-10-26"):
        handler.execute(event, config)

    assert mock_messaging_api.called
    call_args = mock_api_instance.reply_message.call_args
    assert call_args is not None
    reply_request = call_args[0][0]
    messages = reply_request.messages
    assert len(messages) == 3
    assert isinstance(messages[0], TextMessage)
    assert messages[0].text == "戰績數據日期：2026-10-26"
    assert "2026-10-26_combined_hitter.png" in messages[1].original_content_url
    assert "2026-10-26_combined_pitcher.png" in messages[2].original_content_url
