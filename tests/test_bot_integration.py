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
