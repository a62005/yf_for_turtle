import pytest
from unittest.mock import Mock, patch
from src.handlers.dispatcher import CommandDispatcher
from src.handlers.base_handler import BaseHandler

class MockHandler(BaseHandler):
    def __init__(self, can_handle_result=True):
        self._can_handle_result = can_handle_result
        self.executed = False
        
    def can_handle(self, user_text):
        return self._can_handle_result
        
    def execute(self, event, configuration):
        self.executed = True

def test_dispatcher_routes_to_first_capable_handler():
    dispatcher = CommandDispatcher()
    handler1 = MockHandler(False)
    handler2 = MockHandler(True)
    dispatcher.register(handler1)
    dispatcher.register(handler2)
    
    mock_event = Mock()
    mock_event.message.text = "#test"
    mock_config = Mock()
    
    dispatcher.handle(mock_event, mock_config)
    
    assert not handler1.executed
    assert handler2.executed

def test_dispatcher_ignores_if_no_handler():
    dispatcher = CommandDispatcher()
    handler1 = MockHandler(False)
    dispatcher.register(handler1)
    
    mock_event = Mock()
    mock_event.message.text = "#unknown"
    
    # Should not raise exception
    dispatcher.handle(mock_event, Mock())
    assert not handler1.executed
