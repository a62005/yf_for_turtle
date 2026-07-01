import pytest
from unittest.mock import MagicMock, patch
from src.handlers.dispatcher import CommandDispatcher
from src.handlers.base_handler import BaseHandler

def test_dispatcher_permission_interception():
    # 建立一個需要超級管理員權限的 Mock Handler
    class AdminOnlyHandler(BaseHandler):
        def __init__(self):
            super().__init__()
            self.requires_super_admin = True
            self.executed = False
        def can_handle(self, text):
            return text == "#admin_cmd"
        def execute(self, event, config):
            self.executed = True

    # 建立一個需要白名單權限的 Mock Handler
    class WhitelistOnlyHandler(BaseHandler):
        def __init__(self):
            super().__init__()
            self.requires_whitelist = True
            self.executed = False
        def can_handle(self, text):
            return text == "#whitelist_cmd"
        def execute(self, event, config):
            self.executed = True

    dispatcher = CommandDispatcher()
    admin_handler = AdminOnlyHandler()
    whitelist_handler = WhitelistOnlyHandler()
    dispatcher.register(admin_handler)
    dispatcher.register(whitelist_handler)

    mock_event = MagicMock()
    mock_event.source.user_id = "UordinaryUser"
    mock_config = MagicMock()

    # 使用 mock security_manager 進行驗證
    with patch("src.handlers.dispatcher.security_manager") as mock_sm:
        # 情況 A: 發送者非 admin 也非 whitelist
        mock_sm.is_super_admin.return_value = False
        mock_sm.is_whitelisted.return_value = False
        mock_sm.is_league_whitelisted.return_value = False

        # 嘗試執行 admin 指令
        mock_event.message.text = "#admin_cmd"
        dispatcher.handle(mock_event, mock_config)
        assert not admin_handler.executed # 應該被安靜攔截，不執行

        # 嘗試執行 whitelist 指令
        mock_event.message.text = "#whitelist_cmd"
        dispatcher.handle(mock_event, mock_config)
        assert not whitelist_handler.executed # 應該被安靜攔截，不執行

        # 情況 B: 發送者是超級管理員
        mock_sm.is_super_admin.return_value = True
        mock_sm.is_whitelisted.return_value = True # admin 自然 is whitelisted
        mock_sm.is_league_whitelisted.return_value = True

        # 執行 admin 指令
        mock_event.message.text = "#admin_cmd"
        dispatcher.handle(mock_event, mock_config)
        assert admin_handler.executed # 應該成功執行

        # 執行 whitelist 指令
        mock_event.message.text = "#whitelist_cmd"
        dispatcher.handle(mock_event, mock_config)
        assert whitelist_handler.executed # 應該成功執行
