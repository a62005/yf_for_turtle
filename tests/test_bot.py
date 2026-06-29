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
@patch("bot.intent_router")
@patch("time.time")
def test_handle_message_timeout_ignored(mock_time, mock_intent_router, mock_is_processed, mock_event):
    # Event is 1672531199.0s. Now is 1672531220.0s -> 21s delay (> 10s max)
    mock_time.return_value = 1672531220.0
    
    # Late import to prevent side effects before patching
    from bot import handle_message
    handle_message(mock_event)
    
    # The intent_router should be skipped
    mock_intent_router.route.assert_not_called()

@patch("bot.is_token_processed", return_value=False)
@patch("bot.intent_router")
@patch("time.time")
def test_handle_message_under_timeout_processed(mock_time, mock_intent_router, mock_is_processed, mock_event):
    # Event is 1672531199.0s. Now is 1672531204.0s -> 5s delay (< 10s max)
    mock_time.return_value = 1672531204.0
    
    import bot
    bot.handle_message(mock_event)
    
    # The intent_router should be processed normally
    mock_intent_router.route.assert_called_once_with(mock_event, bot.configuration)


@patch("bot.is_token_processed", return_value=False)
@patch("time.time", return_value=1672531204.0)
def test_handle_message_context_var_lifecycle(mock_time, mock_is_processed, mock_event):
    from src.config import current_chat_id
    import bot
    
    # 測試 group
    mock_event.source = MagicMock()
    mock_event.source.type = "group"
    mock_event.source.group_id = "G_test"
    mock_event.source.room_id = "R_test"
    mock_event.source.user_id = "U_test"
    
    captured_chat_id = None
    def mock_route_group(event, config):
        nonlocal captured_chat_id
        captured_chat_id = current_chat_id.get()
        
    with patch("bot.intent_router.route", side_effect=mock_route_group):
        assert current_chat_id.get() is None
        bot.handle_message(mock_event)
        assert captured_chat_id == "G_test"
        assert current_chat_id.get() is None

    # 測試 room
    mock_event.source.type = "room"
    captured_chat_id = None
    def mock_route_room(event, config):
        nonlocal captured_chat_id
        captured_chat_id = current_chat_id.get()
        
    with patch("bot.intent_router.route", side_effect=mock_route_room):
        assert current_chat_id.get() is None
        bot.handle_message(mock_event)
        assert captured_chat_id == "R_test"
        assert current_chat_id.get() is None

    # 測試 user
    mock_event.source.type = "user"
    captured_chat_id = None
    def mock_route_user(event, config):
        nonlocal captured_chat_id
        captured_chat_id = current_chat_id.get()
        
    with patch("bot.intent_router.route", side_effect=mock_route_user):
        assert current_chat_id.get() is None
        bot.handle_message(mock_event)
        assert captured_chat_id == "U_test"
        assert current_chat_id.get() is None

    # 測試 exception 發生時，依然被 reset
    def mock_route_raise(event, config):
        raise ValueError("Route error")
        
    with patch("bot.intent_router.route", side_effect=mock_route_raise):
        assert current_chat_id.get() is None
        with pytest.raises(ValueError):
            bot.handle_message(mock_event)
        assert current_chat_id.get() is None

