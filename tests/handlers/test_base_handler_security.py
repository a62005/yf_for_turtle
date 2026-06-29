from src.handlers.base_handler import BaseHandler

def test_base_handler_security_defaults():
    class DummyHandler(BaseHandler):
        def can_handle(self, text):
            return True
        def execute(self, event, config):
            pass
            
    handler = DummyHandler()
    assert hasattr(handler, "requires_super_admin")
    assert hasattr(handler, "requires_whitelist")
    assert handler.requires_super_admin is False
    assert handler.requires_whitelist is False


def test_base_handler_permission_error_handling():
    from src.fetcher import LeaguePermissionError
    from unittest.mock import MagicMock
    
    class ErrorHandler(BaseHandler):
        def can_handle(self, text):
            return True
        def execute(self, event, config):
            raise LeaguePermissionError("Permission Denied")
            
    handler = ErrorHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    config = MagicMock()
    
    handler.execute(event, config)
    
    handler.reply_text.assert_called_once_with(
        event,
        config,
        "⚠️ 機器人 Yahoo 帳號目前無權限存取此聯盟。請確保已將機器人的 Yahoo 帳號邀請為該聯盟的成員或 Co-manager。"
    )

