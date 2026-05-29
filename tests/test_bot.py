import pytest
from unittest.mock import MagicMock, patch
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.reply_token = "dummy_token"
    event.message = MagicMock()
    event.message.text = "#玩家 肥儒"
    event.timestamp = 1672531199000  # 1672531199.0 seconds Epoch
    return event

@patch("bot.is_token_processed", return_value=False)
@patch("bot.load_config")
@patch("bot.dispatcher")
@patch("time.time")
def test_handle_message_timeout_ignored(mock_time, mock_dispatcher, mock_load_config, mock_is_processed, mock_event):
    # Event is 1672531199.0s. Now is 1672531220.0s -> 21s delay (> 10s max)
    mock_time.return_value = 1672531220.0
    mock_load_config.return_value = {"MAX_EVENT_DELAY_SECONDS": "10.0"}
    
    # Late import to prevent side effects before patching
    from bot import handle_message
    handle_message(mock_event)
    
    # The dispatcher should be skipped
    mock_dispatcher.handle.assert_not_called()

@patch("bot.is_token_processed", return_value=False)
@patch("bot.load_config")
@patch("bot.dispatcher")
@patch("time.time")
def test_handle_message_under_timeout_processed(mock_time, mock_dispatcher, mock_load_config, mock_is_processed, mock_event):
    # Event is 1672531199.0s. Now is 1672531204.0s -> 5s delay (< 10s max)
    mock_time.return_value = 1672531204.0
    mock_load_config.return_value = {"MAX_EVENT_DELAY_SECONDS": "10.0"}
    
    from bot import handle_message
    handle_message(mock_event)
    
    # The dispatcher should be processed normally
    mock_dispatcher.handle.assert_called_once()
