from unittest.mock import MagicMock
from src.handlers.settings_handler import SettingsHandler

def test_settings_handler_can_handle():
    handler = SettingsHandler()
    assert handler.can_handle("#設置") is True
    assert handler.can_handle("設置") is False

def test_settings_handler_execute():
    handler = SettingsHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    config = MagicMock()

    handler.execute(event, config)
    handler.reply_text.assert_called_once()
    
    # 確保回覆內容含有設置字樣
    args, kwargs = handler.reply_text.call_args
    assert "系統設置清單" in args[2]
