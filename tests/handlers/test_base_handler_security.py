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
    from src.config import current_chat_id
    
    class DummyHandler(BaseHandler):
        def can_handle(self, text): return True
        def execute(self, event, config):
            raise LeaguePermissionError("Permission Denied")
            
    handler = DummyHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.source.type = "group"
    event.source.group_id = "C_dummy_group"
    
    # 這裡傳入對應的 dict 作為 configuration/config，相容 wrapped_execute
    config = {
        "YAHOO_CLIENT_ID": "client_123",
        "SERVER_URL": "https://dummy.ngrok.io"
    }
    
    token = current_chat_id.set("C_dummy_group")
    try:
        handler.execute(event, config)
        handler.reply_text.assert_called_once()
        reply_content = handler.reply_text.call_args[0][2]
        
        # 驗證包含授權提示與正確的 Redirect 網址
        assert "無權限存取此聯盟" in reply_content
        assert "api.login.yahoo.com" in reply_content
        assert "client_123" in reply_content
        assert "C_dummy_group" in reply_content  # state 攜帶 chat_id
        assert "https://dummy.ngrok.io/oauth/callback" in reply_content
    finally:
        current_chat_id.reset(token)

