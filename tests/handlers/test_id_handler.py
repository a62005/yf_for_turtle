from unittest.mock import MagicMock
from src.handlers.id_handler import IdHandler

def test_id_handler_can_handle():
    handler = IdHandler()
    assert handler.can_handle("#我的ID") is True
    assert handler.can_handle("我的ID") is False
    assert handler.can_handle("#我的ID extra") is False

def test_id_handler_execute():
    handler = IdHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.source.user_id = "Utest123456"
    config = MagicMock()
    
    handler.execute(event, config)
    handler.reply_text.assert_called_once_with(event, config, "您的 LINE ID 為: Utest123456")
