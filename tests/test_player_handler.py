import pytest
from datetime import datetime
import pytz
from src.handlers.player_handler import PlayerHandler

def test_player_handler_can_handle():
    handler = PlayerHandler()
    assert handler.can_handle("#球員 喇叭") is True
    assert handler.can_handle("#球員") is False
    assert handler.can_handle("#戰績") is False

def test_calculate_target_date_regular():
    handler = PlayerHandler()
    
    # 早上 6:59 查詢 (台北時間 11/12) -> 美西目標日期為 11/10 (台北日期 - 2)
    dt_morning = datetime(2026, 11, 12, 6, 59, 0, tzinfo=pytz.timezone("Asia/Taipei"))
    target_date = handler.calculate_target_date(current_tw_dt=dt_morning, is_offseason=False)
    assert target_date == "2026-11-10"

    # 早上 7:01 查詢 (台北時間 11/12) -> 美西目標日期為 11/11 (台北日期 - 1)
    dt_afternoon = datetime(2026, 11, 12, 7, 1, 0, tzinfo=pytz.timezone("Asia/Taipei"))
    target_date = handler.calculate_target_date(current_tw_dt=dt_afternoon, is_offseason=False)
    assert target_date == "2026-11-11"

    # 晚上 18:00 查詢 (台北時間 11/12) -> 美西目標日期為 11/11 (台北日期 - 1)
    dt_evening = datetime(2026, 11, 12, 18, 0, 0, tzinfo=pytz.timezone("Asia/Taipei"))
    target_date = handler.calculate_target_date(current_tw_dt=dt_evening, is_offseason=False)
    assert target_date == "2026-11-11"

def test_calculate_target_date_offseason():
    handler = PlayerHandler()
    # 休賽季 -> 強制指向設為賽季最後一天
    target_date = handler.calculate_target_date(is_offseason=True, end_date="2026-04-12")
    assert target_date == "2026-04-12"

def test_format_stats():
    handler = PlayerHandler()
    player_info = {
        "english_name": "LeBron James",
        "chinese_name": "勒布朗·詹姆斯",
        "team": "Los Angeles Lakers",
        "jersey_number": "23"
    }
    stats = {
        "FGM/FGA": "14/24",
        "FG%": "0.583",
        "FTM/FTA": "3/4",
        "FT%": "0.750",
        "3PTM": "4",
        "PTS": "35",
        "REB": "9",
        "AST": "12",
        "ST": "2",
        "BLK": "1",
        "TO": "3"
    }
    formatted = handler.format_player_stats(player_info, stats)
    
    expected = (
        "LeBron James (勒布朗·詹姆斯)\n"
        "Los Angeles Lakers#23\n"
        "-----------------------\n"
        "FGM/A :           14/24\n"
        "FG% :             58.3%\n"
        "FTM/A :             3/4\n"
        "FT% :             75.0%\n"
        "3PM :                 4\n"
        "PTS :                35\n"
        "REB :                 9\n"
        "AST :                12\n"
        "STL :                 2\n"
        "BLK :                 1\n"
        "TO :                  3"
    )
    assert formatted.strip() == expected.strip()
