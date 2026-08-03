import time
from unittest.mock import MagicMock, patch
from src.utils.session_manager import (
    register_session,
    get_active_session,
    clear_active_session,
    NicknameSession,
    DraftTimeSession,
    SeasonStartTimeSession,
    LeagueIdSession,
    PrizeSession,
    RemoveLeagueSession,
    AddManagerSession,
    AddWhitelistSession
)

def test_session_lifecycle():
    user_id = "user1"
    # Create a mock session subclassing NicknameSession
    sess = NicknameSession(user_id, "team_abc", duration_sec=10)
    
    register_session(sess)
    active = get_active_session(user_id)
    assert active is sess
    assert active.team_id == "team_abc"
    
    clear_active_session(user_id)
    assert get_active_session(user_id) is None

def test_session_expiry():
    user_id = "user_exp"
    with patch("time.time") as mock_time:
        mock_time.return_value = 1000.0
        sess = NicknameSession(user_id, "team_abc", duration_sec=10)
        register_session(sess)
        
        # Not expired
        mock_time.return_value = 1005.0
        assert get_active_session(user_id) is sess
        
        # Expired
        mock_time.return_value = 1011.0
        assert get_active_session(user_id) is None

@patch("src.utils.session_manager.reply_text")
@patch("src.utils.session_manager.update_team_nickname")
def test_nickname_session_handle(mock_update, mock_reply):
    user_id = "user_nick"
    sess = NicknameSession(user_id, "team123", duration_sec=60)
    
    # Test text starting with # triggers cancellation
    assert sess.handle_message(MagicMock(), MagicMock(), "#設置", MagicMock()) is False
    mock_update.assert_not_called()
    
    # Test valid text sets nickname
    assert sess.handle_message(MagicMock(), MagicMock(), "NewName", MagicMock()) is False
    mock_update.assert_called_once_with("team123", "NewName")
    mock_reply.assert_called_once()

@patch("src.utils.session_manager.reply_text")
@patch("src.utils.session_manager.update_league_settings")
def test_draft_time_session_handle(mock_update, mock_reply):
    user_id = "user_draft"
    sess = DraftTimeSession(user_id, duration_sec=60)
    
    # Test cancellation
    assert sess.handle_message(MagicMock(), MagicMock(), "#", MagicMock()) is False
    
    # Test success path
    with patch("src.llm.llm_agent.LLMAgent.parse_draft_date", return_value={"success": True, "date": "2026-10-15 19:30"}):
        assert sess.handle_message(MagicMock(), MagicMock(), "明天晚上七點半", MagicMock()) is False
        mock_update.assert_called_once_with({"DRAFT_DATE": "2026-10-15 19:30"})
        
    # Test failure path (validation error, keeps session active)
    mock_update.reset_mock()
    with patch("src.llm.llm_agent.LLMAgent.parse_draft_date", return_value={"success": False, "date": None}):
        assert sess.handle_message(MagicMock(), MagicMock(), "invalid time text", MagicMock()) is True
        mock_update.assert_not_called()

@patch("src.utils.session_manager.reply_text")
@patch("src.utils.session_manager.update_league_settings")
def test_season_start_time_session_handle(mock_update, mock_reply):
    user_id = "user_season"
    sess = SeasonStartTimeSession(user_id, duration_sec=60)
    
    # Test success path
    with patch("src.llm.llm_agent.LLMAgent.parse_draft_date", return_value={"success": True, "date": "2026-10-22 08:00"}):
        assert sess.handle_message(MagicMock(), MagicMock(), "下週四早上八點", MagicMock()) is False
        mock_update.assert_called_once_with({"SEASON_START_DATE": "2026-10-22 08:00"})

def test_league_id_session_handle():
    user_id = "user_lid"
    sess = LeagueIdSession(user_id, "nba", duration_sec=60)
    assert sess.sport == "nba"
    
    event = MagicMock()
    event.message = MagicMock()
    dispatcher = MagicMock()
    
    assert sess.handle_message(event, MagicMock(), "12345", dispatcher) is False
    assert event.message.text == "#設置聯盟ID 12345"
    dispatcher.handle.assert_called_once()

@patch("src.utils.session_manager.reply_text")
def test_prize_session_handle(mock_reply):
    user_id = "user_prize"
    sess = PrizeSession(user_id, duration_sec=60)
    
    # Cancellation
    assert sess.handle_message(MagicMock(), MagicMock(), "#", MagicMock()) is False
    # Normal text input prompts to send image
    assert sess.handle_message(MagicMock(), MagicMock(), "hello", MagicMock()) is True
    
    # Image handling delegates to handler
    dispatcher = MagicMock()
    mock_handler = MagicMock()
    dispatcher.get_handler.return_value = mock_handler
    
    assert sess.handle_image(MagicMock(), MagicMock(), b"imagebytes", dispatcher) is False
    mock_handler.handle_image.assert_called_once()

def test_remove_league_session_handle():
    user_id = "user_remove"
    sess = RemoveLeagueSession(user_id, duration_sec=60)
    
    # Ignores general messages
    assert sess.handle_message(MagicMock(), MagicMock(), "hello", MagicMock()) is False
    
    # Triggers on correct command
    event = MagicMock()
    event.message = MagicMock()
    dispatcher = MagicMock()
    assert sess.handle_message(event, MagicMock(), "#確定移除聯盟ID", dispatcher) is False
    dispatcher.handle.assert_called_once()

@patch("src.utils.session_manager.reply_text")
def test_add_manager_session_flow(mock_reply):
    user_id = "user_add_mgr"
    sess = AddManagerSession(user_id, duration_sec=60)
    
    # Step 1: invalid LINE ID
    assert sess.handle_message(MagicMock(), MagicMock(), "invalid_id", MagicMock()) is True
    assert sess.step == 1
    
    # Step 1: cancel
    assert sess.handle_message(MagicMock(), MagicMock(), "#", MagicMock()) is False
    
    # Step 1: valid LINE ID -> transition to step 2
    sess = AddManagerSession(user_id, duration_sec=60)
    valid_id = "U" + "a" * 32
    assert sess.handle_message(MagicMock(), MagicMock(), valid_id, MagicMock()) is True
    assert sess.step == 2
    assert sess.target_id == valid_id
    
    # Step 2: empty name
    assert sess.handle_message(MagicMock(), MagicMock(), "   ", MagicMock()) is True
    
    # Step 2: successful save
    with patch("src.utils.security.security_manager.add_manager") as mock_add:
        assert sess.handle_message(MagicMock(), MagicMock(), "ManagerName", MagicMock()) is False
        mock_add.assert_called_once_with(valid_id, "ManagerName")

@patch("src.utils.session_manager.reply_text")
def test_add_whitelist_session_flow(mock_reply):
    user_id = "user_add_wl"
    sess = AddWhitelistSession(user_id, duration_sec=60)
    
    # Step 1: valid LINE ID -> transition to step 2
    valid_id = "U" + "b" * 32
    assert sess.handle_message(MagicMock(), MagicMock(), valid_id, MagicMock()) is True
    assert sess.step == 2
    
    with patch("src.utils.security.security_manager.add_to_league_whitelist") as mock_add_wl, \
         patch("src.config.load_config", return_value={"LEAGUE_ID": "12345"}):
        assert sess.handle_message(MagicMock(), MagicMock(), "MemberName", MagicMock()) is False
        mock_add_wl.assert_called_once_with("12345", valid_id, "MemberName")
