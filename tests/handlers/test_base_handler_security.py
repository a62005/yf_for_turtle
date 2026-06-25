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
