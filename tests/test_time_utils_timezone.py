import pytest
from datetime import datetime
import pytz
from src.utils.time_utils import is_winter_time_pacific, get_target_date, is_stats_query_allowed

def test_is_winter_time_pacific_override(mocker):
    # 測試環境變數覆蓋為冬令時
    mocker.patch("src.config.load_config", return_value={"IS_WINTER_TIME": True})
    assert is_winter_time_pacific() is True

    # 測試環境變數覆蓋為夏令時
    mocker.patch("src.config.load_config", return_value={"IS_WINTER_TIME": False})
    assert is_winter_time_pacific() is False

def test_get_target_date_dst_boundaries(mocker):
    # 模擬為夏令時
    mocker.patch("src.utils.time_utils.is_winter_time_pacific", return_value=False)
    
    # 夏令跨日點為 7:00
    # 早上 06:59 查詢 -> 台北日期 4/5 減去 2 天 = 4/3
    dt_morning = datetime(2026, 4, 5, 6, 59, 0)
    assert get_target_date(is_offseason=False, current_tw_dt=dt_morning) == "2026-04-03"

    # 早上 07:01 查詢 -> 台北日期 4/5 減去 1 天 = 4/4
    dt_afternoon = datetime(2026, 4, 5, 7, 1, 0)
    assert get_target_date(is_offseason=False, current_tw_dt=dt_afternoon) == "2026-04-04"

def test_get_target_date_standard_boundaries(mocker):
    # 模擬為冬令時
    mocker.patch("src.utils.time_utils.is_winter_time_pacific", return_value=True)
    
    # 冬令跨日點為 8:00
    # 早上 07:59 查詢 -> 台北日期 4/5 減去 2 天 = 4/3
    dt_morning = datetime(2026, 4, 5, 7, 59, 0)
    assert get_target_date(is_offseason=False, current_tw_dt=dt_morning) == "2026-04-03"

    # 早上 08:01 查詢 -> 台北日期 4/5 減去 1 天 = 4/4
    dt_afternoon = datetime(2026, 4, 5, 8, 1, 0)
    assert get_target_date(is_offseason=False, current_tw_dt=dt_afternoon) == "2026-04-04"

def test_is_stats_query_allowed_dst(mocker):
    # 模擬為夏令時 (限時 14:00)
    mocker.patch("src.utils.time_utils.is_winter_time_pacific", return_value=False)
    # 模擬外部 API 回傳 None (走降級備援機制)
    mocker.patch("src.utils.time_utils.check_nba_game_status", return_value=None)
    
    # 模擬台北時間 13:59
    mock_dt = datetime(2026, 4, 5, 13, 59, 0, tzinfo=pytz.timezone("Asia/Taipei"))
    mocker.patch("src.utils.time_utils.datetime", mocker.Mock(now=lambda tz: mock_dt))
    allowed, msg = is_stats_query_allowed(is_offseason=False)
    assert allowed is False
    assert "14:00" in msg

    # 模擬台北時間 14:01
    mock_dt_ok = datetime(2026, 4, 5, 14, 1, 0, tzinfo=pytz.timezone("Asia/Taipei"))
    mocker.patch("src.utils.time_utils.datetime", mocker.Mock(now=lambda tz: mock_dt_ok))
    allowed, _ = is_stats_query_allowed(is_offseason=False)
    assert allowed is True

def test_is_stats_query_allowed_standard(mocker):
    # 模擬為冬令時 (限時 15:00)
    mocker.patch("src.utils.time_utils.is_winter_time_pacific", return_value=True)
    # 模擬外部 API 回傳 None (走降級備援機制)
    mocker.patch("src.utils.time_utils.check_nba_game_status", return_value=None)
    
    # 模擬台北時間 14:59
    mock_dt = datetime(2026, 4, 5, 14, 59, 0, tzinfo=pytz.timezone("Asia/Taipei"))
    mocker.patch("src.utils.time_utils.datetime", mocker.Mock(now=lambda tz: mock_dt))
    allowed, msg = is_stats_query_allowed(is_offseason=False)
    assert allowed is False
    assert "15:00" in msg
