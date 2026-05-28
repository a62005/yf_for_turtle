import pytest
from datetime import datetime
import pytz
from src.handlers.player_handler import PlayerHandler

def test_player_handler_can_handle(mocker):
    mocker.patch("src.handlers.player_handler.load_config", return_value={"GEMINI_API_KEY": "dummy_key"})
    handler = PlayerHandler()
    assert handler.can_handle("#球員 喇叭") is True
    assert handler.can_handle("#球員") is False
    assert handler.can_handle("#戰績") is False

def test_player_handler_can_handle_disabled(mocker):
    mocker.patch("src.handlers.player_handler.load_config", return_value={"GEMINI_API_KEY": None})
    handler = PlayerHandler()
    assert handler.can_handle("#球員 喇叭") is False

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
        "stat_4": "14",
        "stat_3": "24",
        "FG%": "0.583",
        "stat_7": "3",
        "stat_6": "4",
        "FT%": "0.750",
        "3PTM": "4",
        "PTS": "35",
        "REB": "9",
        "AST": "12",
        "ST": "2",
        "BLK": "1",
        "TO": "3"
    }
    formatted = handler.format_player_stats(player_info, stats, "2026-11-12")
    
    # 斷言回傳必須是字典格式 (Flex Message)
    assert isinstance(formatted, dict)
    assert formatted["type"] == "bubble"
    
    # 驗證 Header 部分的球員英文名稱與隊伍背號
    header_box = formatted["header"]["contents"]
    assert header_box[0]["text"] == "LeBron James"
    assert header_box[1]["text"] == "Los Angeles Lakers#23"
    assert header_box[2]["text"] == "2026-11-12"
    
    # 驗證 Body 部分的數據格線對齊
    daily_stats_box = formatted["body"]["contents"][0]["contents"]
    # FGM/A 列
    assert daily_stats_box[0]["contents"][0]["text"] == "FGM/A"
    assert daily_stats_box[0]["contents"][1]["text"] == "14/24"
    assert daily_stats_box[0]["contents"][1]["align"] == "end"
    
    # PTS 列
    assert daily_stats_box[5]["contents"][0]["text"] == "PTS"
    assert daily_stats_box[5]["contents"][1]["text"] == "35"
    assert daily_stats_box[5]["contents"][1]["align"] == "end"
