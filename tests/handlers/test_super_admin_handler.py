import pytest
from unittest.mock import MagicMock, patch
from src.handlers.super_admin_handler import SuperAdminHandler

def test_super_admin_handler_can_handle():
    handler = SuperAdminHandler()
    assert handler.can_handle("#新增白名單 U1234567890abcdef1234567890abcdef") is True
    assert handler.can_handle("#新增白名單") is True
    assert handler.can_handle("新增白名單") is False

def test_super_admin_handler_execute_success():
    handler = SuperAdminHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#新增白名單 U1234567890abcdef1234567890abcdef"
    config = MagicMock()

    with patch("src.handlers.super_admin_handler.security_manager") as mock_sm:
        mock_sm.add_to_whitelist.return_value = True
        handler.execute(event, config)
        
        mock_sm.add_to_whitelist.assert_called_once_with("U1234567890abcdef1234567890abcdef")
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "成功將 ID 加入白名單：U1234567890abcdef1234567890abcdef"
        )

def test_super_admin_handler_execute_invalid_format():
    handler = SuperAdminHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#新增白名單 invalid_format_id"
    config = MagicMock()

    handler.execute(event, config)
    handler.reply_text.assert_called_once_with(
        event, 
        config, 
        "格式錯誤，請使用：#新增白名單 <LINE_ID>"
    )
