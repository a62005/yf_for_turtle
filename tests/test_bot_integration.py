import pytest
from unittest.mock import MagicMock, patch
import bot

@pytest.fixture(autouse=True)
def mock_bound_league():
    with patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "mock_league_123"}):
        yield


@patch('src.handlers.intent_router.IntentRouter.route')
def test_bot_webhook_calls_intent_router(mock_route):
    # Mock Event
    event = MagicMock()
    event.reply_token = "dummy_token"
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.timestamp = None
    
    # 呼叫 bot 的 handle_message
    with patch('bot.is_token_processed', return_value=False):
        bot.handle_message(event)
        
    mock_route.assert_called_once_with(event, bot.configuration)


@patch('src.handlers.intent_router.IntentRouter.route_image')
def test_bot_handle_image_message_without_session(mock_route_image):
    event = MagicMock()
    event.reply_token = "dummy_token"
    event.source.type = "user"
    event.source.user_id = "test_user_no_session"

    with patch('bot.is_token_processed', return_value=False):
        bot.handle_image_message(event)

    mock_route_image.assert_not_called()


@patch('src.handlers.intent_router.IntentRouter.route_image')
def test_bot_handle_image_message_with_prize_session(mock_route_image):
    from src.utils.session_manager import register_session, PrizeSession, clear_active_session
    user_id = "test_user_prize"
    register_session(PrizeSession(user_id, duration_sec=60))

    try:
        event = MagicMock()
        event.reply_token = "dummy_token_2"
        event.source.type = "user"
        event.source.user_id = user_id

        with patch('bot.is_token_processed', return_value=False):
            bot.handle_image_message(event)

        mock_route_image.assert_called_once_with(event, bot.configuration)
    finally:
        clear_active_session(user_id)
