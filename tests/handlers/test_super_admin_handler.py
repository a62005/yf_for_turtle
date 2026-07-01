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

    with patch("src.handlers.super_admin_handler.set_add_manager_session") as mock_set_session:
        handler.execute(event, config)
        
        mock_set_session.assert_called_once_with("U12345", step=1, duration_sec=60)
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "請在 60 秒內輸入欲新增的管理員 LINE ID（例如：U123456...），或輸入 # 取消："
        )

