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


def test_is_stats_query_allowed_offseason():
    from src.utils.time_utils import is_stats_query_allowed
    allowed, msg = is_stats_query_allowed(is_offseason=True)
    assert allowed is True
    assert msg == ""


def test_is_stats_query_allowed_espn_success():
    from unittest.mock import patch
    from src.utils.time_utils import is_stats_query_allowed
    # 模擬 ESPN 回傳阻擋
    with patch("src.utils.time_utils.check_nba_game_status", return_value=(False, "目前仍有比賽正在進行")):
        allowed, msg = is_stats_query_allowed(is_offseason=False, target_date="2026-06-24")
        assert allowed is False
        assert msg == "currently_in_progress_msg" or msg == "目前仍有比賽正在進行"


def test_is_stats_query_allowed_fallback_blocked():
    from unittest.mock import patch, MagicMock
    from src.utils.time_utils import is_stats_query_allowed
    # 模擬 ESPN 失敗 (回傳 None)
    with patch("src.utils.time_utils.check_nba_game_status", return_value=None):
        # 模擬冬令時間且台北時間為早上 10 點 (尚未到 15:00)
        with patch("src.utils.time_utils.is_winter_time_pacific", return_value=True):
            mock_now = MagicMock()
            mock_now.hour = 10
            with patch("src.utils.time_utils.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_now
                mock_datetime.strptime = datetime.strptime # 保持 strptime 正常運作
                
                allowed, msg = is_stats_query_allowed(is_offseason=False, target_date="2026-06-24")
                assert allowed is False
                assert "請於 15:00 後再進行查詢。" in msg


def test_is_stats_query_allowed_fallback_allowed():
    from unittest.mock import patch, MagicMock
    from src.utils.time_utils import is_stats_query_allowed
    # 模擬 ESPN 失敗 (回傳 None)
    with patch("src.utils.time_utils.check_nba_game_status", return_value=None):
        # 模擬冬令時間且台北時間為下午 16 點 (已過 15:00)
        with patch("src.utils.time_utils.is_winter_time_pacific", return_value=True):
            mock_now = MagicMock()
            mock_now.hour = 16
            with patch("src.utils.time_utils.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_now
                mock_datetime.strptime = datetime.strptime
                
                allowed, msg = is_stats_query_allowed(is_offseason=False, target_date="2026-06-24")
                assert allowed is True
                assert msg == ""


def test_fetch_daily_game_times_tw_with_games():
    from unittest.mock import patch, MagicMock
    from src.utils.time_utils import fetch_daily_game_times_tw

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        # 2026-11-04 UTC 23:30 -> 台北 2026-11-05 07:30 (第一場)
        # 2026-11-05 UTC 03:00 -> 台北 2026-11-05 11:00 (最後一場)
        mock_response.json.return_value = {
            "events": [
                {"date": "2026-11-05T03:00Z", "status": {"type": {"state": "pre"}}},
                {"date": "2026-11-04T23:30Z", "status": {"type": {"state": "post"}}},
            ]
        }
        mock_get.return_value = mock_response

        info = fetch_daily_game_times_tw("nba", "2026-11-05")
        assert info is not None
        assert info["has_games"] is True
        assert info["first_game_time"] == "07:30"
        assert info["last_game_time"] == "11:00"
        assert info["query_open_time"] == "13:00"
        assert info["base_update_time"] == "12:55"


def test_fetch_daily_game_times_tw_no_games():
    from unittest.mock import patch, MagicMock
    from src.utils.time_utils import fetch_daily_game_times_tw

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"events": []}
        mock_get.return_value = mock_response

        info = fetch_daily_game_times_tw("nba", "2026-11-05")
        assert info is not None
        assert info["has_games"] is False
        assert info["first_game_time"] is None
        assert info["last_game_time"] is None


def test_fetch_daily_game_times_tw_api_failure():
    from unittest.mock import patch
    import requests
    from src.utils.time_utils import fetch_daily_game_times_tw

    with patch("requests.get", side_effect=requests.RequestException("Timeout")):
        info = fetch_daily_game_times_tw("nba", "2026-11-05")
        assert info is None


def test_resolve_latest_active_tw_date_looks_back_across_consecutive_no_game_days(tmp_path):
    from unittest.mock import patch
    from src.utils.time_utils import resolve_latest_active_tw_date

    # 模擬台灣 11/25、11/24 連兩天皆無比賽 (has_games=False)，最後一天有比賽是 11/23
    def fake_fetch(sport, tw_date_str):
        if tw_date_str in ("2026-11-25", "2026-11-24"):
            return {"date": tw_date_str, "has_games": False}
        return {"date": tw_date_str, "has_games": True}

    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.utils.time_utils.fetch_daily_game_times_tw", side_effect=fake_fetch):
        resolved = resolve_latest_active_tw_date("nba", "2026-11-25", league_id="nba.l.49432")
        assert resolved == "2026-11-23"


def test_resolve_latest_active_tw_date_prefers_local_non_zero_data_when_today_has_no_games(tmp_path):
    import json
    from unittest.mock import patch
    from src.utils.time_utils import resolve_latest_active_tw_date

    daily_dir = tmp_path / "league" / "nba" / "49432" / "daily"
    daily_dir.mkdir(parents=True)
    # 寫入美西 2026-11-21 (對應台灣 2026-11-22) 的有效非 0 數據
    (daily_dir / "date_2026-11-21.json").write_text(
        json.dumps({"date": "2026-11-21", "team_stats": [{"team_id": "1", "stats": {"Today Player": 5, "PTS": 98}}]}),
        encoding="utf-8",
    )
    # 寫入美西 2026-11-23 (對應台灣 2026-11-24) 的全 0 無效殘留檔 -> 應被忽略
    (daily_dir / "date_2026-11-23.json").write_text(
        json.dumps({"date": "2026-11-23", "team_stats": [{"team_id": "1", "stats": {"Today Player": 0, "PTS": 0}}]}),
        encoding="utf-8",
    )

    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.utils.time_utils.fetch_daily_game_times_tw", return_value={"date": "2026-11-25", "has_games": False}):
        resolved = resolve_latest_active_tw_date("nba", "2026-11-25", league_id="nba.l.49432")
        assert resolved == "2026-11-22"



