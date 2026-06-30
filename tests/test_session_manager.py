import time
from unittest.mock import patch
from src.utils.session_manager import (
    set_session,
    get_session,
    clear_session,
    set_nickname_session,
    get_nickname_session,
    clear_nickname_session,
    set_draft_time_session,
    get_draft_time_session,
    clear_draft_time_session,
)

def test_nickname_session():
    user_id = "user1"
    team_id = "team1"
    
    # 測試設定與取得
    set_nickname_session(user_id, team_id, duration_sec=10)
    session = get_nickname_session(user_id)
    assert session is not None
    assert session["team_id"] == team_id
    
    # 測試清除
    clear_nickname_session(user_id)
    assert get_nickname_session(user_id) is None

def test_draft_time_session():
    user_id = "user1"
    draft_data = "2026-06-29 20:00"
    
    # 測試設定與取得
    set_draft_time_session(user_id, draft_data, duration_sec=10)
    data = get_draft_time_session(user_id)
    assert data == draft_data
    
    # 測試清除
    clear_draft_time_session(user_id)
    assert get_draft_time_session(user_id) is None

def test_session_expiry():
    user_id = "user2"
    data = "some_data"
    
    with patch("time.time") as mock_time:
        mock_time.return_value = 1000.0
        set_session(user_id, "draft_time", data, duration_sec=10)
        
        # 時間未超時 (1005.0 < 1010.0)
        mock_time.return_value = 1005.0
        assert get_session(user_id, "draft_time") == data
        
        # 時間已超時 (1011.0 > 1010.0)
        mock_time.return_value = 1011.0
        assert get_session(user_id, "draft_time") is None

def test_prize_session():
    # 測試獎金設定會話的設定、讀取與清除
    user_id = "user_prize_test"
    
    # 測試設定與讀取
    from src.utils.session_manager import set_prize_session, get_prize_session, clear_prize_session
    set_prize_session(user_id, duration_sec=10)
    data = get_prize_session(user_id)
    assert data == {"active": True}
    
    # 測試清除
    clear_prize_session(user_id)
    assert get_prize_session(user_id) is None

