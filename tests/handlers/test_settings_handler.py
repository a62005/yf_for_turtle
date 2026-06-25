from unittest.mock import MagicMock, patch
from src.handlers.settings_handler import SettingsHandler

def test_settings_handler_can_handle():
    handler = SettingsHandler()
    assert handler.can_handle("#設置") is True
    assert handler.can_handle("設置") is False

def test_settings_handler_execute():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()

    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        assert "設置選單" in args[2]

