import pytest
from datetime import datetime
import pytz
from src.utils.time_utils import get_fantasy_week, get_pacific_date

def test_get_fantasy_week():
    start_date = "2025-10-21" # A Tuesday
    # Week 1 starts from 10-21 until next Monday 00:00 PT
    
    tz = pytz.timezone("US/Pacific")
    # Same week Sunday 23:59 PT
    dt1 = tz.localize(datetime(2025, 10, 26, 23, 59, 59))
    assert get_fantasy_week(start_date, current_dt=dt1) == 1
    
    # Next week Monday 00:00 PT
    dt2 = tz.localize(datetime(2025, 10, 27, 0, 0, 0))
    assert get_fantasy_week(start_date, current_dt=dt2) == 2

def test_get_pacific_date():
    date_str = get_pacific_date()
    assert len(date_str) == 10
    datetime.strptime(date_str, "%Y-%m-%d")


def test_check_nba_game_status_empty():
    from unittest.mock import patch, MagicMock
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"events": []}
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is True
        assert msg == ""

def test_check_nba_game_status_in_progress():
    from unittest.mock import patch, MagicMock
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"status": {"type": {"state": "post"}}},
                {"status": {"type": {"state": "in"}}}
            ]
        }
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is False
        assert msg == "目前仍有比賽正在進行"

def test_check_nba_game_status_all_pre():
    from unittest.mock import patch, MagicMock
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"status": {"type": {"state": "pre"}}},
                {"status": {"type": {"state": "pre"}}}
            ]
        }
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is False
        assert msg == "今日比賽尚未開始"

def test_check_nba_game_status_mixed_pre_post():
    from unittest.mock import patch, MagicMock
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"status": {"type": {"state": "post"}}},
                {"status": {"type": {"state": "pre"}}}
            ]
        }
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is False
        assert msg == "今日比賽尚未全部結束，請在所有比賽結束後再進行查詢"

def test_check_nba_game_status_all_post():
    from unittest.mock import patch, MagicMock
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"status": {"type": {"state": "post"}}},
                {"status": {"type": {"state": "post"}}}
            ]
        }
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is True
        assert msg == ""

def test_check_nba_game_status_exception():
    from unittest.mock import patch
    import requests
    with patch("requests.get", side_effect=requests.RequestException("Connection error")):
        from src.utils.time_utils import check_nba_game_status
        result = check_nba_game_status("2026-06-24")
        assert result is None
