import pytest
from unittest.mock import MagicMock, patch
from src.handlers.super_admin_handler import SuperAdminHandler

def test_super_admin_handler_can_handle():
    handler = SuperAdminHandler()
    assert handler.can_handle("#新增管理員") is True
    assert handler.can_handle("新增管理員") is False
    assert handler.can_handle("#新增白名單") is False

def test_super_admin_handler_execute_success():
    handler = SuperAdminHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.source.user_id = "U12345"
    event.message.text = "#新增管理員"
    config = MagicMock()

    from src.utils.session_manager import AddManagerSession
    with patch("src.handlers.super_admin_handler.register_session") as mock_register:
        handler.execute(event, config)
        
        mock_register.assert_called_once()
        args = mock_register.call_args[0]
        assert isinstance(args[0], AddManagerSession)
        assert args[0].user_id == "U12345"
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "請在 60 秒內輸入欲新增的管理員 LINE ID（例如：U123456...），或輸入 # 取消："
        )

