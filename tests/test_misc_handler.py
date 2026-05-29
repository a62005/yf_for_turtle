import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import pytz
import os

from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, TextMessage, ImageMessage

# Import the handler (this will fail initially because the file doesn't exist yet, or we'll create the empty file/class to allow import but fail the assertions)
from src.handlers.misc_handler import MiscHandler

@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.reply_token = "dummy_reply_token"
    event.message = MagicMock()
    return event

@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)

def test_misc_handler_can_handle():
    handler = MiscHandler()
    assert handler.can_handle("#開季") is True
    assert handler.can_handle("#選秀") is True
    assert handler.can_handle("#獎金") is True
    assert handler.can_handle("#幫助") is True
    assert handler.can_handle("#help") is True
    assert handler.can_handle("#Help") is True
    assert handler.can_handle("#HELP") is True
    assert handler.can_handle("  #help  ") is True
    
    assert handler.can_handle("#開季啦") is False
    assert handler.can_handle("#開季 ") is True # Since we strip the user text, this should be True
    assert handler.can_handle("#其他") is False
    assert handler.can_handle("開季") is False

def test_calculate_countdown():
    handler = MiscHandler()
    
    # Let's mock datetime now inside _calculate_countdown or patch datetime in pytz/datetime
    # Target time in the future
    # Let's mock datetime.now to return a fixed Taipei time: 2026-05-29 08:00:00
    taipei_tz = pytz.timezone("Asia/Taipei")
    fixed_now = taipei_tz.localize(datetime(2026, 5, 29, 8, 0, 0))
    
    with patch("src.handlers.misc_handler.datetime") as mock_datetime:
        # Mock datetime.now(taipei_tz)
        mock_datetime.now.return_value = fixed_now
        # Also need strptime to work normally
        mock_datetime.strptime = datetime.strptime
        
        # Test countdown to future
        res = handler._calculate_countdown("2026-05-30 09:30:00")
        assert res == "1 天 1 小時 30 分鐘"
        
        # Test target time reached
        res_reached = handler._calculate_countdown("2026-05-29 07:00:00")
        assert res_reached == "已經到達！"

@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_season_start(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    
    # 1. Not offseason -> silently ignore
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-04-10" # before end_date
    mock_event.message.text = "#開季"
    
    handler.execute(mock_event, mock_config)
    mock_api_client.assert_not_called()
    
    # 2. Offseason, but NEXT_SEASON_START_DATE not set -> silently ignore
    mock_get_pacific.return_value = "2026-05-29" # after end_date
    mock_load_config.return_value = {"NEXT_SEASON_START_DATE": None}
    
    handler.execute(mock_event, mock_config)
    mock_api_client.assert_not_called()
    
    # 3. Offseason and NEXT_SEASON_START_DATE set -> reply countdown
    mock_load_config.return_value = {"NEXT_SEASON_START_DATE": "2026-10-20 08:00:00"}
    
    # Mock _calculate_countdown to return stable string
    with patch.object(handler, "_calculate_countdown", return_value="140 天 5 小時 20 分鐘") as mock_calc:
        handler.execute(mock_event, mock_config)
        mock_calc.assert_called_with("2026-10-20 08:00:00")
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.reply_token == "dummy_reply_token"
        assert reply_req.messages[0].text == "🏀 距離 2026-27 新賽季開季還有：\n👉 140 天 5 小時 20 分鐘"

@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_draft(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    
    # 1. Not offseason -> silently ignore
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-04-10"
    mock_event.message.text = "#選秀"
    
    handler.execute(mock_event, mock_config)
    mock_api_client.assert_not_called()
    
    # 2. Offseason, and DRAFT_DATE set -> reply countdown
    mock_get_pacific.return_value = "2026-05-29"
    mock_load_config.return_value = {"DRAFT_DATE": "2026-10-15 10:00:00"}
    
    with patch.object(handler, "_calculate_countdown", return_value="135 天 7 小時 0 分鐘") as mock_calc:
        handler.execute(mock_event, mock_config)
        mock_calc.assert_called_with("2026-10-15 10:00:00")
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.messages[0].text == "⚔️ 距離 2026-27 聯盟選秀還有：\n👉 135 天 7 小時 0 分鐘"

@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_prize(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    mock_event.message.text = "#獎金"
    
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    
    # 1. Missing PRIZE_IMAGE_PATH or SERVER_URL -> silently ignore
    mock_load_config.return_value = {"PRIZE_IMAGE_PATH": None, "SERVER_URL": "http://localhost:5000"}
    handler.execute(mock_event, mock_config)
    mock_api_client.assert_not_called()
    
    # 2. Path not existing -> silently ignore
    mock_load_config.return_value = {"PRIZE_IMAGE_PATH": "non_existent.png", "SERVER_URL": "http://localhost:5000"}
    handler.execute(mock_event, mock_config)
    mock_api_client.assert_not_called()
    
    # 3. Path exists -> Reply ImageMessage
    with patch("os.path.exists", return_value=True):
        mock_load_config.return_value = {"PRIZE_IMAGE_PATH": "data/images/bonus.png", "SERVER_URL": "http://localhost:5000"}
        handler.execute(mock_event, mock_config)
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert isinstance(reply_req.messages[0], ImageMessage)
        assert reply_req.messages[0].original_content_url == "https://localhost:5000/images/bonus.png"
        assert reply_req.messages[0].preview_image_url == "https://localhost:5000/images/bonus.png"

@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_help(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    mock_event.message.text = "#幫助"
    
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    
    with patch("logging.info") as mock_logging:
        handler.execute(mock_event, mock_config)
        mock_logging.assert_called()
        mock_api_client.assert_not_called()
