import pytest
import os
import json
from unittest.mock import MagicMock, patch, mock_open
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

from src.handlers.set_league_id_handler import SetLeagueIdHandler
from src.handlers.dispatcher import CommandDispatcher
from src.utils.security import security_manager

@pytest.fixture(autouse=True)
def mock_data_dir(tmp_path):
    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)):
        yield

@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.reply_token = "dummy_token"
    event.message = MagicMock()
    event.message.text = "#設置聯盟ID 12345"
    event.source = MagicMock()
    event.source.user_id = "test_user_manager"
    return event

@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)

def test_set_league_id_non_manager_blocked_no_league(mock_event, mock_config):
    """A non-manager is blocked by the dispatcher when LEAGUE_ID is not set yet."""
    dispatcher = CommandDispatcher()
    handler = SetLeagueIdHandler()
    dispatcher.register(handler)

    with patch("src.config.load_config", return_value={"LEAGUE_ID": None}), \
         patch.object(security_manager, "is_manager", return_value=False), \
         patch.object(security_manager, "is_super_admin", return_value=False):
        
        with patch.object(handler, "execute") as mock_execute:
            dispatcher.handle(mock_event, mock_config)
            mock_execute.assert_not_called()

def test_set_league_id_non_manager_blocked_with_league(mock_event, mock_config):
    """A non-manager is blocked by the dispatcher when LEAGUE_ID is already set."""
    dispatcher = CommandDispatcher()
    handler = SetLeagueIdHandler()
    dispatcher.register(handler)

    with patch("src.config.load_config", return_value={"LEAGUE_ID": "nba.l.999"}), \
         patch.object(security_manager, "is_league_manager", return_value=False), \
         patch.object(security_manager, "is_super_admin", return_value=False):
        
        with patch.object(handler, "execute") as mock_execute:
            dispatcher.handle(mock_event, mock_config)
            mock_execute.assert_not_called()

def test_set_league_id_manager_tries_bound_by_other_manager_blocked(mock_event, mock_config):
    """If a manager tries to bind a league ID already owned by another manager, it is blocked."""
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()

    # Pre-configure league roles to have an owner
    mock_roles = {
        "nba.l.12345": {
            "manager": "other_manager_user_id",
            "whitelist": {}
        }
    }

    with patch("src.config.load_config", return_value={"YAHOO_CLIENT_ID": "id", "YAHOO_CLIENT_SECRET": "sec"}), \
         patch.object(security_manager, "_load_json", return_value=mock_roles), \
         patch.object(security_manager, "is_super_admin", return_value=False):
        
        handler.execute(mock_event, mock_config)
        handler.reply_text.assert_called_once_with(
            mock_event,
            mock_config,
            "⚠️ 設置失敗，該聯盟 ID (nba.l.12345) 已由其他管理員管理。"
        )

def test_set_league_id_manager_binds_new_league_becomes_owner(mock_event, mock_config, tmp_path):
    """If a manager binds a new league ID, they become the owner."""
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()

    # Empty roles initially
    mock_roles = {}
    saved_roles = {}

    def mock_load(path, default):
        if "league_roles" in str(path):
            return mock_roles
        return default

    def mock_save(path, data):
        nonlocal saved_roles
        if "league_roles" in str(path):
            saved_roles = data
            return True
        return False

    mock_team = MagicMock()
    mock_team.team_id = "1"
    mock_team.name = "官方測試隊伍"
    mock_league = MagicMock()
    mock_league.teams.return_value = [mock_team]

    with patch("src.config.load_config", return_value={"YAHOO_CLIENT_ID": "id", "YAHOO_CLIENT_SECRET": "sec"}), \
         patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch.object(security_manager, "_load_json", side_effect=mock_load), \
         patch.object(security_manager, "_save_json", side_effect=mock_save), \
         patch.object(security_manager, "is_super_admin", return_value=False), \
         patch("src.handlers.set_league_id_handler.sync_season_metadata") as mock_sync, \
         patch("src.handlers.set_league_id_handler.open", mock_open()) as mock_file, \
         patch("src.handlers.set_league_id_handler.os.path.exists", return_value=False), \
         patch("yahoofantasy.League", return_value=mock_league):
         
        handler.execute(mock_event, mock_config)
        
        mock_sync.assert_called_once()
        assert saved_roles.get("nba.l.12345") == {"manager": "test_user_manager", "whitelist": {}, "authorized": False}
        handler.reply_text.assert_called_once_with(
            mock_event,
            mock_config,
            "✅ 成功將此聊天室綁定至聯賽 ID：nba.l.12345"
        )
