import pytest
from unittest.mock import MagicMock, patch
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

from src.handlers.base_handler import BaseHandler
from src.handlers.dispatcher import CommandDispatcher
from src.utils.security import security_manager

# Define dummy handlers for testing
class DummySuperAdminHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_super_admin = True
        self.executed = False

    def can_handle(self, user_text: str) -> bool:
        return user_text == "#admin"

    def execute(self, event, configuration) -> None:
        self.executed = True

class DummyManagerHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_manager = True
        self.executed = False

    def can_handle(self, user_text: str) -> bool:
        return user_text == "#manager"

    def execute(self, event, configuration) -> None:
        self.executed = True

class DummyWhitelistHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.executed = False

    def can_handle(self, user_text: str) -> bool:
        return user_text == "#whitelist"

    def execute(self, event, configuration) -> None:
        self.executed = True

@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.reply_token = "dummy_token"
    event.message = MagicMock()
    event.message.text = ""
    event.source = MagicMock()
    event.source.user_id = "test_user"
    return event

@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)

# --- Requires Super Admin Tests ---

def test_dispatcher_super_admin_authorized(mock_event, mock_config):
    dispatcher = CommandDispatcher()
    handler = DummySuperAdminHandler()
    dispatcher.register(handler)

    mock_event.message.text = "#admin"
    
    with patch.object(security_manager, "is_super_admin", return_value=True) as mock_auth:
        dispatcher.handle(mock_event, mock_config)
        mock_auth.assert_called_once_with("test_user")
        assert handler.executed is True

def test_dispatcher_super_admin_unauthorized(mock_event, mock_config):
    dispatcher = CommandDispatcher()
    handler = DummySuperAdminHandler()
    dispatcher.register(handler)

    mock_event.message.text = "#admin"
    
    with patch.object(security_manager, "is_super_admin", return_value=False) as mock_auth:
        dispatcher.handle(mock_event, mock_config)
        mock_auth.assert_called_once_with("test_user")
        assert handler.executed is False

# --- Requires Manager Tests ---

def test_dispatcher_manager_league_exists_authorized(mock_event, mock_config):
    dispatcher = CommandDispatcher()
    handler = DummyManagerHandler()
    dispatcher.register(handler)

    mock_event.message.text = "#manager"
    
    with patch("src.config.load_config", return_value={"LEAGUE_ID": "nba.l.999"}), \
         patch.object(security_manager, "is_league_manager", return_value=True) as mock_auth:
        dispatcher.handle(mock_event, mock_config)
        mock_auth.assert_called_once_with("test_user", "nba.l.999")
        assert handler.executed is True

def test_dispatcher_manager_league_exists_unauthorized(mock_event, mock_config):
    dispatcher = CommandDispatcher()
    handler = DummyManagerHandler()
    dispatcher.register(handler)

    mock_event.message.text = "#manager"
    
    with patch("src.config.load_config", return_value={"LEAGUE_ID": "nba.l.999"}), \
         patch.object(security_manager, "is_league_manager", return_value=False) as mock_auth:
        dispatcher.handle(mock_event, mock_config)
        mock_auth.assert_called_once_with("test_user", "nba.l.999")
        assert handler.executed is False

def test_dispatcher_manager_league_empty_authorized(mock_event, mock_config):
    dispatcher = CommandDispatcher()
    handler = DummyManagerHandler()
    dispatcher.register(handler)

    mock_event.message.text = "#manager"
    
    with patch("src.config.load_config", return_value={"LEAGUE_ID": None}), \
         patch.object(security_manager, "is_manager", return_value=True) as mock_auth:
        dispatcher.handle(mock_event, mock_config)
        mock_auth.assert_called_once_with("test_user")
        assert handler.executed is True

def test_dispatcher_manager_league_empty_unauthorized(mock_event, mock_config):
    dispatcher = CommandDispatcher()
    handler = DummyManagerHandler()
    dispatcher.register(handler)

    mock_event.message.text = "#manager"
    
    with patch("src.config.load_config", return_value={"LEAGUE_ID": ""}), \
         patch.object(security_manager, "is_manager", return_value=False) as mock_auth:
        dispatcher.handle(mock_event, mock_config)
        mock_auth.assert_called_once_with("test_user")
        assert handler.executed is False

# --- Requires Whitelist Tests ---

def test_dispatcher_whitelist_authorized(mock_event, mock_config):
    dispatcher = CommandDispatcher()
    handler = DummyWhitelistHandler()
    dispatcher.register(handler)

    mock_event.message.text = "#whitelist"
    
    with patch("src.config.load_config", return_value={"LEAGUE_ID": "nba.l.999"}), \
         patch.object(security_manager, "is_league_whitelisted", return_value=True) as mock_auth:
        dispatcher.handle(mock_event, mock_config)
        mock_auth.assert_called_once_with("test_user", "nba.l.999")
        assert handler.executed is True

def test_dispatcher_whitelist_unauthorized(mock_event, mock_config):
    dispatcher = CommandDispatcher()
    handler = DummyWhitelistHandler()
    dispatcher.register(handler)

    mock_event.message.text = "#whitelist"
    
    with patch("src.config.load_config", return_value={"LEAGUE_ID": "nba.l.999"}), \
         patch.object(security_manager, "is_league_whitelisted", return_value=False) as mock_auth:
        dispatcher.handle(mock_event, mock_config)
        mock_auth.assert_called_once_with("test_user", "nba.l.999")
        assert handler.executed is False
