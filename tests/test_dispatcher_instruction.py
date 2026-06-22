import pytest
from src.handlers.base_handler import BaseHandler
from src.handlers.dispatcher import CommandDispatcher

class DummyHandler(BaseHandler):
    @property
    def instruction_desc(self) -> str:
        return "- #測試指令: 測試用"
    def can_handle(self, user_text: str) -> bool:
        return False
    def execute(self, event, configuration) -> None:
        pass

def test_dispatcher_gets_all_instructions():
    dispatcher = CommandDispatcher()
    dispatcher.register(DummyHandler())
    assert dispatcher.get_all_instruction_descs() == "- #測試指令: 測試用"
